"""
Test suite for error mapping and resilient error handling in MCP server.

This test suite ensures the MCP server never crashes the connection, even when the backend API fails. It tests various failure scenarios including HTTP errors, authentication failures, and timeouts.
"""

import os
import sys
import pytest
import httpx

# add parent directory to path in order to import server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# we must set environment variables BEFORE importing server module
os.environ["BACKEND_URL_HOST"] = "http://localhost"
os.environ["BACKEND_URL_PORT"] = "5000"

from server import analyze_dependencies


class FakeRequest:
    """Fake `httpx.Request` for error testing."""

    def __init__(self, url="http://localhost:5000/analyze"):
        self.url = url


class FakeResponse:
    """Fake `httpx.Response` for testing error scenarios."""

    def __init__(
        self, json_data=None, status_code=200, should_raise=False, error_detail=None
    ):
        self._json_data = json_data or {}
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
                f"HTTP {self.status_code}", request=self.request, response=self
            )


class FakeClient:
    """Fake `httpx.Client` for testing."""

    def __init__(self, response=None, should_timeout=False):
        self.response = response
        self.should_timeout = should_timeout
        self.post_calls = []

    def post(self, url, **kwargs):
        # record the POST call for verification
        self.post_calls.append((url, kwargs))

        # simulate timeout, if configured
        if self.should_timeout:
            raise httpx.ReadTimeout("Request timed out")

        return self.response

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@pytest.fixture
def test_inputs():
    """Standard test input data"""
    return {
        "project_name": "test-project",
        "requirements_content": "requests==2.28.0\nflask==2.3.0",
        "user_token": "test-token-12345",
    }


def test_500_error_returns_error_result_not_exception(monkeypatch, test_inputs):
    """
    Tests that when the backend API returns a 500 error, the function:
    1. does NOT raise an uncaught Python exception (like `httpx.HTTPStatusError`),
    2. returns a dict with 'isError=True', and
    3. allows the AI agent to see the error and retry, rather than crashing.
    """
    # create fake response that simulates a 500 error
    fake_response = FakeResponse(
        json_data={},
        status_code=500,
        should_raise=True,
        error_detail="Internal server error occurred",
    )
    fake_client = FakeClient(fake_response)

    # replace httpx.Client with our fake
    monkeypatch.setattr("server.httpx.Client", lambda: fake_client)

    # call `analyze_dependencies` - this should NOT raise an exception
    result = analyze_dependencies(
        project_name=test_inputs["project_name"],
        requirements_content=test_inputs["requirements_content"],
        user_token=test_inputs["user_token"],
    )

    # assert the function returned a result (didn't crash)
    assert result is not None

    # assert the result indicates an error occurred
    assert isinstance(result, dict), "Result must be a dictionary"
    assert result.get("isError") is True, "Result must have isError=True"

    # assert the error message is present and informative
    assert "error" in result, "Result must contain 'error' key"
    error_message = result["error"]
    assert "500" in error_message or "Internal server error" in error_message, (
        "Error message should mention the 500 status or server error"
    )

    # verify the HTTP call was attempted
    assert len(fake_client.post_calls) > 0, "Should have attempted to call the backend"


def test_401_unauthorized_returns_clear_message(monkeypatch, test_inputs):
    """
    Tests that when the backend API returns a 401 error, the function:
    1. returns a dict with 'isError=True',
    2. contains a clear message about authorization failure, and
    3. helps the AI Agent know to ask the user for a new token.

    NOTE: the error message must explicitly contain "Authorization failed" or "Invalid token"
    """
    # create fake response that simulates a 401 error
    fake_response = FakeResponse(
        json_data={},
        status_code=401,
        should_raise=True,
        error_detail="Invalid or expired token",
    )
    fake_client = FakeClient(fake_response)

    # replace `httpx.Client` with our mock
    monkeypatch.setattr("server.httpx.Client", lambda: fake_client)

    # call analyze_dependencies
    result = analyze_dependencies(
        project_name=test_inputs["project_name"],
        requirements_content=test_inputs["requirements_content"],
        user_token=test_inputs["user_token"],
    )

    # assert that the function returned an error result
    assert result is not None
    assert isinstance(result, dict), "Result must be a dictionary"
    assert result.get("isError") is True, "Result must have isError=True"

    # assert that the error message explicitly mentions authorization failure
    assert "error" in result, "Result must contain 'error' key"
    error_message = result["error"].lower()

    # check for specific authorization-related keywords
    has_auth_message = (
        "authorization failed" in error_message
        or "invalid token" in error_message
        or "unauthorized" in error_message
        or "401" in error_message
    )
    assert has_auth_message, (
        f"Error message must contain authorization failure info. Got: {result['error']}"
    )


def test_timeout_returns_user_friendly_message(monkeypatch, test_inputs):
    """
    Tests that when the backend API times out, the function:
    1. catches the httpx.ReadTimeout exception,
    2. returns a dict with isError=True, and
    3. provides a user-friendly message: "The analysis timed out. Please try again."

    NOTE: this ensures timeouts don't crash the MCP connection
    """
    # create fake client that simulates a timeout
    fake_client = FakeClient(should_timeout=True)

    # replace `httpx.Client` with our mock
    monkeypatch.setattr("server.httpx.Client", lambda: fake_client)

    # call analyze_dependencies - should handle timeout gracefully
    result = analyze_dependencies(
        project_name=test_inputs["project_name"],
        requirements_content=test_inputs["requirements_content"],
        user_token=test_inputs["user_token"],
    )

    # assert that the function returned an error result
    assert result is not None
    assert isinstance(result, dict), "Result must be a dictionary"
    assert result.get("isError") is True, "Result must have isError=True"

    # assert that the error message is user-friendly and mentions timeout
    assert "error" in result, "Result must contain 'error' key"
    error_message = result["error"]

    # check for the specific timeout message
    assert "timed out" in error_message.lower() or "timeout" in error_message.lower(), (
        f"Error message must mention timeout. Got: {error_message}"
    )

    assert "try again" in error_message.lower() or "retry" in error_message.lower(), (
        f"Error message should suggest retrying. Got: {error_message}"
    )


def test_403_forbidden_returns_error_result(monkeypatch, test_inputs):
    """
    Tests that other HTTP errors (like 403) are also handled gracefully.
    """
    # create fake response that simulates a 403 error
    fake_response = FakeResponse(
        json_data={},
        status_code=403,
        should_raise=True,
        error_detail="Access forbidden",
    )
    fake_client = FakeClient(fake_response)

    # replace `httpx.Client` with our mock
    monkeypatch.setattr("server.httpx.Client", lambda: fake_client)

    # call analyze_dependencies
    result = analyze_dependencies(
        project_name=test_inputs["project_name"],
        requirements_content=test_inputs["requirements_content"],
        user_token=test_inputs["user_token"],
    )

    assert result is not None
    assert isinstance(result, dict), "Result must be a dictionary"
    assert result.get("isError") is True, "Result must have isError=True"
    assert "error" in result, "Result must contain 'error' key"
    assert "403" in result["error"] or "forbidden" in result["error"].lower(), (
        "Error message should mention the 403 status or forbidden"
    )


def test_network_error_returns_error_result(monkeypatch, test_inputs):
    """
    Tests that network errors (httpx.RequestError) are handled gracefully.
    """

    class FakeClientWithNetworkError:
        """Fake client that raises a network error."""

        def post(self, url, **kwargs):
            raise httpx.ConnectError("Connection refused")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    # replace `httpx.Client` with our mock
    monkeypatch.setattr("server.httpx.Client", lambda: FakeClientWithNetworkError())

    # call analyze_dependencies
    result = analyze_dependencies(
        project_name=test_inputs["project_name"],
        requirements_content=test_inputs["requirements_content"],
        user_token=test_inputs["user_token"],
    )

    assert result is not None
    assert isinstance(result, dict), "Result must be a dictionary"
    assert result.get("isError") is True, "Result must have isError=True"
    assert "error" in result, "Result must contain 'error' key"

    error_message = result["error"].lower()
    assert (
        "connection" in error_message
        or "network" in error_message
        or "request" in error_message
    ), f"Error message should mention connection/network issue. Got: {result['error']}"
