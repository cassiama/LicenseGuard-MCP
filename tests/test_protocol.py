"""
Test suite for MCP protocol compliance.

This test suite validates the MCP server's protocol compliance by:
- verifying tool discovery and schema validation
- testing serialization with complex inputs (emojis, newlines, quotes, non-ASCII)
- ensuring protocol compliance (CallToolResult structure, content types, error handling)

NOTE: tests use the FastMCP instance directly (not subprocess) to validate MCP protocol types and serialization
"""

import os
import sys
import pytest
import httpx

# add parent directory to path to import server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# set environment variables BEFORE importing server module
os.environ["BACKEND_URL_HOST"] = "http://localhost"
os.environ["BACKEND_URL_PORT"] = "5000"

from server import mcp, analyze_dependencies


class FakeRequest:
    """Fake httpx.Request for mocking backend responses."""

    def __init__(self, url="http://localhost:5000/analyze"):
        self.url = url


class FakeResponse:
    """Fake httpx.Response for mocking backend API."""

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
                f"HTTP {self.status_code}",
                request=self.request, # type: ignore
                response=self,  # type: ignore
            )


class FakeClient:
    """Fake httpx.Client for mocking backend API calls."""

    def __init__(self, response):
        self.response = response
        self.post_calls = []

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return self.response

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@pytest.mark.asyncio
async def test_tool_discovery():
    """
    Test that analyze_dependencies tool is discoverable via FastMCP.

    Validates:
    - tool name is present in the tool registry
    - tool's JSON schema includes required parameters
    - parameter types and descriptions are correct
    """
    # get list of tools from FastMCP instance
    tools = await mcp.list_tools()

    # extract tool names
    tool_names = [tool.name for tool in tools]

    # assert analyze_dependencies is present
    assert "analyze_dependencies" in tool_names, (
        f"Tool 'analyze_dependencies' not found. Available tools: {tool_names}"
    )

    # find the analyze_dependencies tool
    analyze_tool = next(
        (tool for tool in tools if tool.name == "analyze_dependencies"), None
    )
    assert analyze_tool is not None, "analyze_dependencies tool not found"

    # validate the tool's input schema
    assert hasattr(analyze_tool, "inputSchema"), "Tool must have inputSchema"
    schema = analyze_tool.inputSchema

    # check that required parameters are present
    assert "properties" in schema, "Schema must have properties"
    properties = schema["properties"]

    assert "project_name" in properties, "Schema must include project_name parameter"
    assert properties["project_name"]["type"] == "string", (
        "project_name must be of type string"
    )

    assert "requirements_content" in properties, (
        "Schema must include requirements_content parameter"
    )
    assert properties["requirements_content"]["type"] == "string", (
        "requirements_content must be of type string"
    )

    assert "user_token" in properties, "Schema must include user_token parameter"
    assert properties["user_token"]["type"] == "string", (
        "user_token must be of type string"
    )

    # validate required fields
    assert "required" in schema, "Schema must specify required fields"
    required_fields = schema["required"]
    assert "project_name" in required_fields, "project_name must be required"
    assert "requirements_content" in required_fields, (
        "requirements_content must be required"
    )
    assert "user_token" in required_fields, "user_token must be required"


def test_nasty_input_serialization(monkeypatch):
    """
    Test serialization with complex "nasty" inputs.

    This test validates that the MCP protocol correctly handles:
    - emojis (🛡️)
    - newlines (\\n)
    - double quotes (")
    - non-ASCII characters (ü, ö, etc.)

    The test ensures:
    - no JSONDecodeError or ValidationError is raised,
    - the result can be serialized/deserialized correctly, and
    - the protocol handles encoding/decoding correctly
    """
    # mock successful backend response
    mock_response_data = {
        "project_name": "test-nasty-🛡️-project",
        "analysis_date": "2025-12-14",
        "files": [
            {
                "name": "requests",
                "version": "2.28.0",
                "license": "Apache-2.0",
                "confidence": 0.9,
            }
        ],
    }
    fake_response = FakeResponse(mock_response_data)
    fake_client = FakeClient(fake_response)

    # replace httpx.Client with our fake
    monkeypatch.setattr("server.httpx.Client", lambda: fake_client)

    # create "nasty" input with emojis, newlines, quotes, and non-ASCII
    nasty_requirements = """# Test with 🛡️ emoji security
requests==2.28.0  # "quoted" comment
flask>=2.0.0

pandas==1.5.0
münchen-package==1.0.0  # non-ASCII city name
café-lib==2.0.0  # accented characters
"""

    # call the tool with nasty inputs
    # NOTE: this should NOT raise JSONDecodeError or ValidationError
    try:
        result = analyze_dependencies(
            project_name="test-nasty-🛡️-project",
            requirements_content=nasty_requirements,
            user_token='test-token-with-"quotes"-and-🔑-emoji',
        )
    except Exception as e:
        pytest.fail(
            f"Tool call raised unexpected exception: {type(e).__name__}: {str(e)}"
        )

    # verify the result is a dict (FastMCP will wrap this in CallToolResult)
    assert isinstance(result, dict), f"Result must be dict, got {type(result)}"

    # verify the result has expected structure
    assert "project_name" in result, "Result must have project_name"
    assert result["project_name"] == "test-nasty-🛡️-project", (
        "Project name with emoji should be preserved"
    )

    # verify the fake client was called with nasty inputs
    assert len(fake_client.post_calls) == 1, "Should have made one HTTP call"
    url, kwargs = fake_client.post_calls[0]

    # verify the nasty inputs were properly encoded in the request
    assert "files" in kwargs, "Request must include files"
    assert "data" in kwargs, "Request must include data"


def test_protocol_compliance_success(monkeypatch):
    """
    Verify MCP protocol compliance for successful responses.

    This test validates that when FastMCP wraps the tool result:
    - the result would be wrapped in CallToolResult by FastMCP
    - the content would be list of TextContent
    - no encoding issues with the response

    NOTE: We test the raw function output here. FastMCP automatically wraps
    this in the proper MCP types (CallToolResult, TextContent) when serving.
    """
    # mock successful backend response
    mock_response_data = {
        "project_name": "protocol-test",
        "analysis_date": "2025-12-14",
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
                "confidence": 0.95,
            },
        ],
    }
    fake_response = FakeResponse(mock_response_data)
    fake_client = FakeClient(fake_response)

    # replace httpx.Client with our fake
    monkeypatch.setattr("server.httpx.Client", lambda: fake_client)

    # call the tool
    result = analyze_dependencies(
        project_name="protocol-test",
        requirements_content="requests==2.28.0\nflask==2.3.0",
        user_token="test-token-12345",
    )

    # verify result is a dict (FastMCP will wrap this)
    assert isinstance(result, dict), f"Result must be dict, got {type(result)}"

    # verify result structure matches expected API response
    assert "project_name" in result, "Result must have project_name"
    assert "analysis_date" in result, "Result must have analysis_date"
    assert "files" in result, "Result must have files"
    assert isinstance(result["files"], list), "files must be a list"
    assert len(result["files"]) == 2, "Should have 2 dependencies"

    # verify each file entry has required fields
    for file_entry in result["files"]:
        assert "name" in file_entry, "File entry must have name"
        assert "version" in file_entry, "File entry must have version"
        assert "license" in file_entry, "File entry must have license"
        assert "confidence" in file_entry, "File entry must have confidence"

        # verify types
        assert isinstance(file_entry["name"], str), "name must be string"
        assert isinstance(file_entry["version"], str), "version must be string"
        assert isinstance(file_entry["license"], str), "license must be string"
        assert isinstance(file_entry["confidence"], (int, float)), (
            "confidence must be numeric"
        )


def test_protocol_compliance_error(monkeypatch):
    """
    Verify MCP protocol compliance for error responses.

    When the backend fails or validation fails, the response should:
    - be a dict with 'error' and 'isError' fields
    - have isError=True
    - contain a descriptive error message
    - not crash or raise unhandled exceptions

    NOTE: FastMCP will wrap this in CallToolResult with isError=True
    """
    # mock backend error response
    fake_response = FakeResponse(
        json_data={},
        status_code=500,
        should_raise=True,
        error_detail="Internal server error",
    )
    fake_client = FakeClient(fake_response)

    # replace httpx.Client with our fake
    monkeypatch.setattr("server.httpx.Client", lambda: fake_client)

    # call the tool - should return error dict, not raise exception
    result = analyze_dependencies(
        project_name="error-test",
        requirements_content="requests==2.28.0",
        user_token="test-token",
    )

    # verify result is a dict with error information
    assert isinstance(result, dict), f"Error result must be dict, got {type(result)}"

    # verify error structure
    assert "isError" in result, "Error result must have 'isError' field"
    assert result["isError"] is True, "isError must be True for error responses"

    assert "error" in result, "Error result must have 'error' field"
    assert isinstance(result["error"], str), "error must be a string"
    assert len(result["error"]) > 0, "error message must not be empty"

    # verify error message mentions the status code or error type
    error_message = result["error"]
    assert "500" in error_message or "error" in error_message.lower(), (
        f"Error message should mention the error type. Got: {error_message}"
    )


def test_validation_error_protocol_compliance():
    """
    Test that validation errors also comply with MCP protocol.

    When input validation fails, the response should:
    - raise a RuntimeError (which FastMCP will catch and wrap)
    - contain a descriptive error message
    """
    # test with invalid project name (empty string)
    with pytest.raises(RuntimeError) as exc_info:
        analyze_dependencies(
            project_name="",  # too short
            requirements_content="requests==2.28.0",
            user_token="test-token",
        )

    # verify error message is descriptive
    error_message = str(exc_info.value)
    assert "Project name must be between 1 and 100 characters" in error_message, (
        f"Error message should describe validation failure. Got: {error_message}"
    )

    # test with project name that's too long
    with pytest.raises(RuntimeError) as exc_info:
        analyze_dependencies(
            project_name="a" * 101,  # too long
            requirements_content="requests==2.28.0",
            user_token="test-token",
        )

    error_message = str(exc_info.value)
    assert "Project name must be between 1 and 100 characters" in error_message


def test_unicode_edge_cases(monkeypatch):
    """
    Test additional Unicode edge cases to ensure robust serialization.

    Tests:
    - right-to-left text (Arabic, Hebrew)
    - emoji combinations
    - zero-width characters
    - mathematical alphanumeric symbols
    """
    # mock successful backend response
    mock_response_data = {
        "project_name": "unicode-test-🌍",
        "analysis_date": "2025-12-14",
        "files": [
            {
                "name": "requests",
                "version": "2.28.0",
                "license": "Apache-2.0",
                "confidence": 0.9,
            }
        ],
    }
    fake_response = FakeResponse(mock_response_data)
    fake_client = FakeClient(fake_response)

    # replace httpx.Client with our fake
    monkeypatch.setattr("server.httpx.Client", lambda: fake_client)

    # create input with various Unicode edge cases
    unicode_requirements = """# مرحبا (Arabic: Hello)
requests==2.28.0  # שלום (Hebrew: Hello)
flask>=2.0.0  # 👨‍👩‍👧‍👦 family emoji
pandas==1.5.0  # Zero-width: a​b (has zero-width space)
numpy==1.24.0  # 𝕌𝕟𝕚𝕔𝕠𝕕𝕖 (mathematical alphanumeric symbols)
"""

    # call the tool with Unicode edge cases
    try:
        result = analyze_dependencies(
            project_name="unicode-test-🌍",
            requirements_content=unicode_requirements,
            user_token="token-🔐-secure",
        )
    except Exception as e:
        pytest.fail(f"Unicode handling failed: {type(e).__name__}: {str(e)}")

    # verify result is valid
    assert isinstance(result, dict), f"Result must be dict, got {type(result)}"
    assert "project_name" in result, "Result must have project_name"

    # verify Unicode was preserved in the response
    assert result["project_name"] == "unicode-test-🌍", (
        "Unicode emoji in project name should be preserved"
    )


def test_timeout_error_protocol_compliance(monkeypatch):
    """
    Test that timeout errors are handled gracefully and comply with protocol.
    """

    class FakeClientWithTimeout:
        """Fake client that raises timeout error."""

        def post(self, url, **kwargs):
            raise httpx.ReadTimeout("Request timed out")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    # replace httpx.Client with our fake
    monkeypatch.setattr("server.httpx.Client", lambda: FakeClientWithTimeout())

    # call the tool, which should return error dict, not raise exception
    result = analyze_dependencies(
        project_name="timeout-test",
        requirements_content="requests==2.28.0",
        user_token="test-token",
    )

    # verify result is a dict with error information
    assert isinstance(result, dict), f"Timeout result must be dict, got {type(result)}"
    assert "isError" in result, "Timeout result must have 'isError' field"
    assert result["isError"] is True, "isError must be True for timeout"
    assert "error" in result, "Timeout result must have 'error' field"

    # verify error message mentions timeout
    error_message = result["error"].lower()
    assert "timed out" in error_message or "timeout" in error_message, (
        f"Error message should mention timeout. Got: {result['error']}"
    )
