"""
Test suite for MCP server with mocked HTTP calls.

This test suite uses pytest with custom fake classes to replace httpx components, allowing tests to run in isolation without requiring a backend API or internet connection.
"""

import os
import sys
import pytest
import httpx

# add parent directory to path in order to import server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# we must set environment variables BEFORE importing server module so that the module-level os.getenv() calls in server.py get the correct values
os.environ["BACKEND_URL_HOST"] = "http://localhost"
os.environ["BACKEND_URL_PORT"] = "5000"

from server import analyze_dependencies


class FakeRequest:
    """Fake `httpx.Request` for error testing."""

    def __init__(self, url="http://localhost:5000/analyze"):
        self.url = url


class FakeResponse:
    """Fake `httpx.Response` for testing."""

    def __init__(
        self, json_data, status_code=200, should_raise=False, error_detail=None
    ):
        self._json_data = json_data
        self.status_code = status_code
        self._should_raise = should_raise
        self._error_detail = error_detail
        self.request = FakeRequest()

    def json(self):
        if self._error_detail:
            return {"detail": self._error_detail}
        return self._json_data

    def raise_for_status(self):
        if self._should_raise:
            raise httpx.HTTPStatusError(
                "Bad Request" if self.status_code == 400 else "Error",
                request=self.request,  # type: ignore
                response=self,  # type: ignore
            )


class FakeClient:
    """Fake `httpx.Client` for testing."""

    def __init__(self, response):
        self.response = response
        self.post_calls = []

    def post(self, url, **kwargs):
        # Record the call for verification
        self.post_calls.append((url, kwargs))
        return self.response

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@pytest.fixture
def mock_response_data():
    """Mock response data that mimics the backend API response."""
    return {
        "project_name": "test-project",
        "analysis_date": "2025-10-26",
        "files": [
            {
                "name": "requests",
                "version": "2.28.0",
                "license": "Apache-2.0",
                "confidence": 0.9,
            },
            {
                "name": "flask",
                "version": "2.3.0",
                "license": "BSD-3-Clause",
                "confidence": 0.9,
            },
        ],
    }


@pytest.fixture
def test_inputs():
    """Standard test input data"""
    return {
        "project_name": "test-project",
        "requirements_content": "requests==2.28.0\nflask==2.3.0",
        "user_token": "test-token-12345",
    }


@pytest.fixture
def complex_response_data():
    """More complex mock response for testing parsing"""
    return {
        "project_name": "complex-project",
        "analysis_date": "2025-10-26",
        "files": [
            {
                "name": "numpy",
                "version": "1.24.0",
                "license": "BSD-3-Clause",
                "confidence": 0.99,
            },
            {
                "name": "pandas",
                "version": "2.0.0",
                "license": "BSD-3-Clause",
                "confidence": 0.97,
            },
            {
                "name": "matplotlib",
                "version": "3.7.0",
                "license": "PSF",
                "confidence": 0.92,
            },
        ],
    }


def test_analyze_dependencies_success(monkeypatch, mock_response_data, test_inputs):
    """
    Test that analyze_dependencies correctly handles a successful API response.

    This test:
    1. Uses monkeypatch to replace httpx.Client with a fake
    2. Simulates a successful backend API response
    3. Verifies the function returns the expected parsed result
    4. Ensures the fake client was called with correct parameters
    """
    # create fake response and client
    fake_response = FakeResponse(mock_response_data)
    fake_client = FakeClient(fake_response)

    # replace httpx.Client with a function that returns our fake client
    monkeypatch.setattr("server.httpx.Client", lambda: fake_client)

    # call the analyze_dependencies tool
    result = analyze_dependencies(
        project_name=test_inputs["project_name"],
        requirements_content=test_inputs["requirements_content"],
        user_token=test_inputs["user_token"],
    )

    # verify the result matches our mock response
    assert result == mock_response_data
    assert result["project_name"] == "test-project"
    assert len(result["files"]) == 2

    # verify the first dependency details
    first_dep = result["files"][0]
    assert first_dep["name"] == "requests"
    assert first_dep["version"] == "2.28.0"
    assert first_dep["license"] == "Apache-2.0"
    assert first_dep["confidence"] == 0.9

    # verify the fake client was called correctly
    assert len(fake_client.post_calls) == 1
    url, kwargs = fake_client.post_calls[0]

    # make sure the URL is correct
    assert url == "http://localhost:5000/analyze"

    # check if the headers contain the bearer token in the authorization header
    assert "Authorization" in kwargs["headers"]
    assert kwargs["headers"]["Authorization"] == f"Bearer {test_inputs['user_token']}"

    # check that project_name and requirement.txt file was included in the form data
    assert kwargs["data"]["project_name"] == test_inputs["project_name"]
    assert "file" in kwargs["files"]


def test_analyze_dependencies_validates_project_name(monkeypatch):
    """
    Test that analyze_dependencies validates project name length.

    This ensures validation happens before any HTTP calls are made.
    """
    # create a fake client that won't be used due to validation failure
    fake_client = FakeClient(FakeResponse({}))
    monkeypatch.setattr("server.httpx.Client", lambda: fake_client)

    # test when project name is empty
    with pytest.raises(
        RuntimeError, match="Project name must be between 1 and 100 characters"
    ):
        analyze_dependencies(
            project_name="",
            requirements_content="requests==2.28.0",
            user_token="test-token",
        )

    # test when the project name is too long
    with pytest.raises(
        RuntimeError, match="Project name must be between 1 and 100 characters"
    ):
        analyze_dependencies(
            project_name="a" * 101,
            requirements_content="requests==2.28.0",
            user_token="test-token",
        )

    # verify no HTTP calls were made due to validation failure
    assert len(fake_client.post_calls) == 0


def test_analyze_dependencies_validates_requirements_type(monkeypatch):
    """
    Test that analyze_dependencies validates requirements_content is a string.
    """
    # create a fake client that won't be used due to validation failure
    fake_client = FakeClient(FakeResponse({}))
    monkeypatch.setattr("server.httpx.Client", lambda: fake_client)

    with pytest.raises(
        AssertionError, match="'requirements.txt' file must be of type string"
    ):
        analyze_dependencies(
            project_name="test-project",
            requirements_content=123,  # invalid type
            user_token="test-token",
        )

    # verify no HTTP calls were made
    assert len(fake_client.post_calls) == 0


def test_analyze_dependencies_handles_http_error(monkeypatch, test_inputs):
    """
    Test that analyze_dependencies properly handles HTTP errors from the backend.

    This simulates a 400 Bad Request error from the backend API.
    """
    # create a fake response that raises an HTTP error
    fake_response = FakeResponse(
        json_data={},
        status_code=400,
        should_raise=True,
        error_detail="Invalid request format",
    )
    fake_client = FakeClient(fake_response)

    monkeypatch.setattr("server.httpx.Client", lambda: fake_client)

    # call the analyze_dependencies tool and assert the function returns the error message string
    result = analyze_dependencies(
        project_name=test_inputs["project_name"],
        requirements_content=test_inputs["requirements_content"],
        user_token=test_inputs["user_token"],
    )

    # verify the error message contains the status code and detail
    error_message = str(result)
    assert "400" in error_message
    assert "Invalid request format" in error_message


def test_analyze_dependencies_no_internet_required(
    monkeypatch, mock_response_data, test_inputs
):
    """
    Test that the test suite can run without internet connectivity.

    This is a meta-test that verifies our fake class strategy allows the tests to run in complete isolation (e.g., in CI environments).
    """
    # create fake response and client
    fake_response = FakeResponse(mock_response_data)
    fake_client = FakeClient(fake_response)

    monkeypatch.setattr("server.httpx.Client", lambda: fake_client)

    # call the analyze_dependencies tool- this should work without any network access
    result = analyze_dependencies(
        project_name=test_inputs["project_name"],
        requirements_content=test_inputs["requirements_content"],
        user_token=test_inputs["user_token"],
    )

    # verify we got a result without making real HTTP calls
    assert result is not None
    assert result["project_name"] == "test-project"

    # verify the fake client was used
    assert len(fake_client.post_calls) == 1


def test_analyze_dependencies_parses_response_correctly(
    monkeypatch, complex_response_data
):
    """
    Test that the MCP server correctly parses the backend response.

    This verifies the data flow from fake response -> function return value.
    """
    # setup fake client with complex response
    fake_response = FakeResponse(complex_response_data)
    fake_client = FakeClient(fake_response)

    monkeypatch.setattr("server.httpx.Client", lambda: fake_client)

    # call the analyze_dependencies tool
    result = analyze_dependencies(
        project_name="complex-project",
        requirements_content="numpy==1.24.0\npandas==2.0.0\nmatplotlib==3.7.0",
        user_token="test-token",
    )

    # verify complete parsing
    assert result["project_name"] == "complex-project"
    assert len(result["files"]) == 3

    # verify each dependency was parsed correctly
    dep_names = [dep["name"] for dep in result["files"]]
    assert "numpy" in dep_names
    assert "pandas" in dep_names
    assert "matplotlib" in dep_names
