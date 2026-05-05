"""
Property-based tests for error handling and response format.

Feature: document-upload-auth
Property 13: Error Response Format
"""
import pytest
from hypothesis import given, strategies as st, settings
from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
import json

from app.exceptions import (
    DocumentUploadException,
    AuthenticationException,
    ValidationException,
    StorageException,
    create_error_response,
    document_upload_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    generic_exception_handler
)


class TestErrorResponseFormat:
    """
    Property 13: Error Response Format
    
    For any error (authentication, validation, or storage), the Upload_Service SHALL:
    1. Return a JSON response with error_code and message fields
    2. Use appropriate HTTP status codes (401 for auth, 400 for validation, 500 for storage)
    3. NOT expose internal system paths or stack traces
    
    Validates: Requirements 7.1, 7.2, 7.3, 7.4
    """

    @given(
        error_code=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
        message=st.text(min_size=1, max_size=200).filter(lambda x: x.strip()),
        status_code=st.integers(min_value=400, max_value=599)
    )
    @settings(max_examples=20)
    def test_create_error_response_format(self, error_code, message, status_code):
        """Test that create_error_response always returns proper JSON format."""
        response = create_error_response(error_code, message, status_code)
        
        # Response should be JSONResponse
        assert response.status_code == status_code
        
        # Parse the response content
        content = json.loads(response.body.decode())
        
        # Must have required fields
        assert "error_code" in content
        assert "message" in content
        assert content["error_code"] == error_code
        assert content["message"] == message
        
        # Should not expose sensitive information
        assert "password" not in content.get("details", {})
        assert "secret" not in content.get("details", {})
        assert "key" not in content.get("details", {})

    @given(
        error_code=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
        message=st.text(min_size=1, max_size=200).filter(lambda x: x.strip())
    )
    @settings(max_examples=15)
    def test_authentication_exception_status_code(self, error_code, message):
        """Test that AuthenticationException always returns 401 status code."""
        exc = AuthenticationException(error_code, message)
        
        assert exc.status_code == 401
        assert exc.error_code == error_code
        assert exc.message == message

    @given(
        error_code=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
        message=st.text(min_size=1, max_size=200).filter(lambda x: x.strip())
    )
    @settings(max_examples=15)
    def test_validation_exception_status_code(self, error_code, message):
        """Test that ValidationException always returns 400 status code."""
        exc = ValidationException(error_code, message)
        
        assert exc.status_code == 400
        assert exc.error_code == error_code
        assert exc.message == message

    @given(
        error_code=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
        message=st.text(min_size=1, max_size=200).filter(lambda x: x.strip())
    )
    @settings(max_examples=15)
    def test_storage_exception_status_code(self, error_code, message):
        """Test that StorageException always returns 500 status code."""
        exc = StorageException(error_code, message)
        
        assert exc.status_code == 500
        assert exc.error_code == error_code
        assert exc.message == message

    @given(
        error_code=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
        message=st.text(min_size=1, max_size=200).filter(lambda x: x.strip()),
        details=st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.one_of(st.text(), st.integers(), st.booleans()),
            min_size=0,
            max_size=5
        )
    )
    @settings(max_examples=20)
    async def test_document_upload_exception_handler_format(self, error_code, message, details):
        """Test that DocumentUploadException handler returns proper format."""
        # Create a mock request
        request = type('MockRequest', (), {})()
        
        # Create exception with details
        exc = DocumentUploadException(error_code, message, 500, details)
        
        # Handle the exception
        response = await document_upload_exception_handler(request, exc)
        
        # Parse response
        content = json.loads(response.body.decode())
        
        # Verify format
        assert "error_code" in content
        assert "message" in content
        assert content["error_code"] == error_code
        assert content["message"] == message
        assert response.status_code == 500

    @given(
        status_code=st.sampled_from([400, 401, 404, 500]),
        detail=st.text(min_size=1, max_size=200).filter(lambda x: x.strip())
    )
    @settings(max_examples=15)
    async def test_http_exception_handler_format(self, status_code, detail):
        """Test that HTTPException handler returns proper format."""
        # Create a mock request
        request = type('MockRequest', (), {})()
        
        # Create HTTPException
        exc = HTTPException(status_code=status_code, detail=detail)
        
        # Handle the exception
        response = await http_exception_handler(request, exc)
        
        # Parse response
        content = json.loads(response.body.decode())
        
        # Verify format
        assert "error_code" in content
        assert "message" in content
        assert response.status_code == status_code
        
        # Verify appropriate error codes for status codes
        if status_code == 401:
            assert content["error_code"] == "AUTH_MISSING"
        elif status_code == 400:
            assert content["error_code"] == "VALIDATION_ERROR"
        elif status_code == 404:
            assert content["error_code"] == "NOT_FOUND"
        elif status_code == 500:
            assert content["error_code"] == "INTERNAL_ERROR"

    async def test_validation_exception_handler_format(self):
        """Test that RequestValidationError handler returns proper format."""
        # Create a mock request
        request = type('MockRequest', (), {})()
        
        # Create a mock validation error
        validation_error = {
            "loc": ("body", "field"),
            "msg": "field required",
            "type": "value_error.missing"
        }
        
        # Create RequestValidationError (this is tricky to mock properly)
        # We'll create a simple mock that has the errors() method
        class MockValidationError:
            def errors(self):
                return [validation_error]
        
        exc = MockValidationError()
        
        # Handle the exception
        response = await validation_exception_handler(request, exc)
        
        # Parse response
        content = json.loads(response.body.decode())
        
        # Verify format
        assert "error_code" in content
        assert "message" in content
        assert content["error_code"] == "VALIDATION_ERROR"
        assert response.status_code == 400
        assert "details" in content
        assert "validation_errors" in content["details"]

    @given(
        exception_message=st.text(min_size=1, max_size=200).filter(lambda x: x.strip())
    )
    @settings(max_examples=10)
    async def test_generic_exception_handler_format(self, exception_message):
        """Test that generic exception handler returns proper format and doesn't expose internals."""
        # Create a mock request
        request = type('MockRequest', (), {})()
        
        # Create a generic exception
        exc = Exception(exception_message)
        
        # Handle the exception
        response = await generic_exception_handler(request, exc)
        
        # Parse response
        content = json.loads(response.body.decode())
        
        # Verify format
        assert "error_code" in content
        assert "message" in content
        assert content["error_code"] == "INTERNAL_ERROR"
        assert content["message"] == "An unexpected error occurred"  # Generic message, not exposing internals
        assert response.status_code == 500
        
        # Should NOT expose the actual exception message or stack trace
        assert exception_message not in content["message"]

    @given(
        details=st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.text(min_size=1, max_size=50),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=15)
    def test_sensitive_information_filtering(self, details):
        """Test that sensitive information is filtered from error details."""
        # Add some sensitive keys to the details
        sensitive_details = dict(details)
        sensitive_details.update({
            "password": "secret123",
            "secret_key": "mysecret",
            "auth_token": "token123",
            "api_key": "key456"
        })
        
        response = create_error_response("TEST_ERROR", "Test message", 400, sensitive_details)
        content = json.loads(response.body.decode())
        
        # Sensitive information should be filtered out
        if "details" in content:
            details_content = content["details"]
            assert "password" not in details_content
            assert "secret_key" not in details_content
            assert "auth_token" not in details_content
            assert "api_key" not in details_content
            
            # Non-sensitive details should still be present
            for key, value in details.items():
                if not any(sensitive in key.lower() for sensitive in ['password', 'secret', 'key', 'token', 'auth']):
                    assert key in details_content
                    assert details_content[key] == value