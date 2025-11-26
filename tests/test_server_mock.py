"""
Test suite for MCP server with mocked HTTP calls.

This test suite uses unittest.mock to patch httpx.post calls, allowing tests
to run in isolation without requiring a backend API or internet connection.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import os
import sys

# Add parent directory to path to import server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from server import analyze_dependencies


class TestAnalyzeDependenciesMocked(unittest.TestCase):
    """Test cases for the analyze_dependencies MCP tool with mocked HTTP calls."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Set environment variables for the test
        os.environ['BACKEND_URL_HOST'] = 'http://localhost'
        os.environ['BACKEND_URL_PORT'] = '5000'
        
        # Sample test data
        self.project_name = "test-project"
        self.requirements_content = "requests==2.28.0\nflask==2.3.0"
        self.user_token = "test-token-12345"
        
        # Mock response data that mimics the backend API response
        self.mock_response_data = {
            "project_name": "test-project",
            "dependencies": [
                {
                    "name": "requests",
                    "version": "2.28.0",
                    "license": "Apache-2.0",
                    "confidence": 0.95
                },
                {
                    "name": "flask",
                    "version": "2.3.0",
                    "license": "BSD-3-Clause",
                    "confidence": 0.98
                }
            ],
            "total_dependencies": 2,
            "analysis_timestamp": "2025-11-26T16:30:00Z"
        }

    @patch('server.httpx.Client')
    def test_analyze_dependencies_success(self, mock_client_class):
        """
        Test that analyze_dependencies correctly handles a successful API response.
        
        This test:
        1. Mocks the httpx.Client and its post method
        2. Simulates a successful backend API response
        3. Verifies the function returns the expected parsed result
        4. Ensures the mock was called with correct parameters
        """
        # Create a mock response object
        mock_response = Mock()
        mock_response.json.return_value = self.mock_response_data
        mock_response.raise_for_status = Mock()  # No exception raised
        
        # Create a mock client instance
        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        
        # Configure the mock Client class to return our mock instance
        mock_client_class.return_value.__enter__.return_value = mock_client_instance
        
        # Call the function under test
        result = analyze_dependencies(
            project_name=self.project_name,
            requirements_content=self.requirements_content,
            user_token=self.user_token
        )
        
        # Assertions
        # 1. Verify the result matches our mock response
        self.assertEqual(result, self.mock_response_data)
        self.assertEqual(result["project_name"], "test-project")
        self.assertEqual(result["total_dependencies"], 2)
        self.assertEqual(len(result["dependencies"]), 2)
        
        # 2. Verify the first dependency details
        first_dep = result["dependencies"][0]
        self.assertEqual(first_dep["name"], "requests")
        self.assertEqual(first_dep["version"], "2.28.0")
        self.assertEqual(first_dep["license"], "Apache-2.0")
        self.assertEqual(first_dep["confidence"], 0.95)
        
        # 3. Verify the mock was called correctly
        mock_client_instance.post.assert_called_once()
        call_args = mock_client_instance.post.call_args
        
        # Check the URL
        self.assertEqual(call_args[0][0], "http://localhost:5000/analyze")
        
        # Check the headers contain the authorization token
        self.assertIn("Authorization", call_args[1]["headers"])
        self.assertEqual(call_args[1]["headers"]["Authorization"], f"Bearer {self.user_token}")
        
        # Check the form data
        self.assertEqual(call_args[1]["data"]["project_name"], self.project_name)
        
        # Check that files were included
        self.assertIn("file", call_args[1]["files"])

    @patch('server.httpx.Client')
    def test_analyze_dependencies_validates_project_name(self, mock_client_class):
        """
        Test that analyze_dependencies validates project name length.
        
        This ensures validation happens before any HTTP calls are made.
        """
        # Test empty project name
        with self.assertRaises(RuntimeError) as context:
            analyze_dependencies(
                project_name="",
                requirements_content=self.requirements_content,
                user_token=self.user_token
            )
        self.assertIn("Project name must be between 1 and 100 characters", str(context.exception))
        
        # Test project name too long
        with self.assertRaises(RuntimeError) as context:
            analyze_dependencies(
                project_name="a" * 101,
                requirements_content=self.requirements_content,
                user_token=self.user_token
            )
        self.assertIn("Project name must be between 1 and 100 characters", str(context.exception))
        
        # Verify no HTTP calls were made due to validation failure
        mock_client_class.assert_not_called()

    @patch('server.httpx.Client')
    def test_analyze_dependencies_validates_requirements_type(self, mock_client_class):
        """
        Test that analyze_dependencies validates requirements_content is a string.
        """
        with self.assertRaises(AssertionError) as context:
            analyze_dependencies(
                project_name=self.project_name,
                requirements_content=123,  # Invalid type
                user_token=self.user_token
            )
        self.assertIn("'requirements.txt' file must be of type string", str(context.exception))
        
        # Verify no HTTP calls were made
        mock_client_class.assert_not_called()

    @patch('server.httpx.Client')
    def test_analyze_dependencies_handles_http_error(self, mock_client_class):
        """
        Test that analyze_dependencies properly handles HTTP errors from the backend.
        
        This simulates a 400 Bad Request error from the backend API.
        """
        # Create a mock response that raises an HTTP error
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"detail": "Invalid request format"}
        
        # Configure raise_for_status to raise an HTTPStatusError
        from httpx import HTTPStatusError, Request
        mock_request = Mock(spec=Request)
        mock_request.url = "http://localhost:5000/analyze"
        
        mock_response.request = mock_request
        mock_response.raise_for_status.side_effect = HTTPStatusError(
            "Bad Request",
            request=mock_request,
            response=mock_response
        )
        
        # Create mock client
        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client_instance
        
        # Call the function and expect a RuntimeError
        with self.assertRaises(RuntimeError) as context:
            analyze_dependencies(
                project_name=self.project_name,
                requirements_content=self.requirements_content,
                user_token=self.user_token
            )
        
        # Verify the error message contains the status code and detail
        error_message = str(context.exception)
        self.assertIn("400", error_message)
        self.assertIn("Invalid request format", error_message)

    @patch('server.httpx.Client')
    def test_analyze_dependencies_no_internet_required(self, mock_client_class):
        """
        Test that the test suite can run without internet connectivity.
        
        This is a meta-test that verifies our mocking strategy allows
        the tests to run in complete isolation (e.g., in CI environments).
        """
        # Create a mock response
        mock_response = Mock()
        mock_response.json.return_value = self.mock_response_data
        mock_response.raise_for_status = Mock()
        
        # Create mock client
        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client_instance
        
        # Call the function - this should work without any network access
        result = analyze_dependencies(
            project_name=self.project_name,
            requirements_content=self.requirements_content,
            user_token=self.user_token
        )
        
        # Verify we got a result without making real HTTP calls
        self.assertIsNotNone(result)
        self.assertEqual(result["project_name"], "test-project")
        
        # Verify the mock was used (not real httpx.Client)
        mock_client_class.assert_called_once()

    @patch('server.httpx.Client')
    def test_analyze_dependencies_parses_response_correctly(self, mock_client_class):
        """
        Test that the MCP server correctly parses the mock backend response.
        
        This verifies the data flow from mock response -> function return value.
        """
        # Create a more complex mock response
        complex_response = {
            "project_name": "complex-project",
            "dependencies": [
                {
                    "name": "numpy",
                    "version": "1.24.0",
                    "license": "BSD-3-Clause",
                    "confidence": 0.99
                },
                {
                    "name": "pandas",
                    "version": "2.0.0",
                    "license": "BSD-3-Clause",
                    "confidence": 0.97
                },
                {
                    "name": "matplotlib",
                    "version": "3.7.0",
                    "license": "PSF",
                    "confidence": 0.92
                }
            ],
            "total_dependencies": 3,
            "analysis_timestamp": "2025-11-26T16:35:00Z",
            "warnings": ["Some licenses may require attribution"]
        }
        
        # Setup mock
        mock_response = Mock()
        mock_response.json.return_value = complex_response
        mock_response.raise_for_status = Mock()
        
        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client_instance
        
        # Call function
        result = analyze_dependencies(
            project_name="complex-project",
            requirements_content="numpy==1.24.0\npandas==2.0.0\nmatplotlib==3.7.0",
            user_token=self.user_token
        )
        
        # Verify complete parsing
        self.assertEqual(result["project_name"], "complex-project")
        self.assertEqual(result["total_dependencies"], 3)
        self.assertEqual(len(result["dependencies"]), 3)
        self.assertIn("warnings", result)
        self.assertEqual(len(result["warnings"]), 1)
        
        # Verify each dependency was parsed correctly
        dep_names = [dep["name"] for dep in result["dependencies"]]
        self.assertIn("numpy", dep_names)
        self.assertIn("pandas", dep_names)
        self.assertIn("matplotlib", dep_names)


if __name__ == '__main__':
    unittest.main()
