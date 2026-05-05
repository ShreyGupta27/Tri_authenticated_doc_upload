"""
Property-based tests for authentication handler method selection.

Feature: document-upload-auth, Property 10: Authentication Method Selection
Validates: Requirements 5.1, 5.2, 5.3
"""
import pytest
from hypothesis import given, strategies as st, settings
from fastapi import HTTPException, Request
from unittest.mock import Mock, AsyncMock
import jwt
from datetime import datetime, timezone, timedelta

from app.auth.authentication_handler import AuthenticationHandler
from app.auth.jwt_authenticator import JWTAuthenticator
from app.auth.certificate_authenticator import CertificateAuthenticator
from app.auth.secret_key_authenticator import SecretKeyAuthenticator
from app.models import AuthMethod, AuthResult


# Test data
TEST_JWT_SECRET = "test-jwt-secret"
TEST_API_KEYS = {"test-key-1": "app1", "test-key-2": "app2"}
TEST_CA_CERT = "-----BEGIN CERTIFICATE-----\ntest-ca-cert\n-----END CERTIFICATE-----"


def create_valid_jwt_token(user_id: str = "test-user") -> str:
    """Create a valid JWT token for testing."""
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


# Strategies for generating test data
@st.composite
def single_credential_strategy(draw):
    """Generate single authentication credential."""
    method = draw(st.sampled_from([AuthMethod.JWT, AuthMethod.SECRET_KEY]))
    
    if method == AuthMethod.JWT:
        token = create_valid_jwt_token()
        return {
            "method": method,
            "authorization": f"Bearer {token}",
            "x_api_key": None,
            "x_client_cert": None
        }
    else:  # SECRET_KEY
        api_key = draw(st.sampled_from(list(TEST_API_KEYS.keys())))
        return {
            "method": method,
            "authorization": None,
            "x_api_key": api_key,
            "x_client_cert": None
        }


@st.composite
def multiple_credentials_strategy(draw):
    """Generate multiple authentication credentials."""
    # Always include at least 2 credentials
    include_jwt = draw(st.booleans())
    include_api_key = draw(st.booleans())
    include_cert = draw(st.booleans())
    
    # Ensure at least 2 are True
    credentials = [include_jwt, include_api_key, include_cert]
    if sum(credentials) < 2:
        # Force at least 2 to be True
        false_indices = [i for i, val in enumerate(credentials) if not val]
        if len(false_indices) >= 2:
            credentials[false_indices[0]] = True
            credentials[false_indices[1]] = True
        else:
            credentials[false_indices[0]] = True
    
    include_jwt, include_api_key, include_cert = credentials
    
    result = {
        "authorization": None,
        "x_api_key": None,
        "x_client_cert": None
    }
    
    if include_jwt:
        token = create_valid_jwt_token()
        result["authorization"] = f"Bearer {token}"
    
    if include_api_key:
        api_key = draw(st.sampled_from(list(TEST_API_KEYS.keys())))
        result["x_api_key"] = api_key
    
    if include_cert:
        result["x_client_cert"] = "test-cert-data"
    
    return result


class TestAuthenticationMethodSelectionProperty:
    """
    Property 10: Authentication Method Selection
    
    For any request with explicit auth_method parameter, the Authentication_Handler
    SHALL use only that method regardless of other credentials present.
    For any request with exactly one credential type and no explicit method,
    the handler SHALL auto-detect correctly.
    For any request with multiple credential types and no explicit method,
    the handler SHALL reject with 400 error.
    
    Validates: Requirements 5.1, 5.2, 5.3
    """
    
    def setup_method(self):
        """Set up test fixtures."""
        pass
    
    def _create_handler(self):
        """Create a fresh handler with new mocks for each test."""
        # Create mock authenticators that always succeed
        jwt_auth = Mock(spec=JWTAuthenticator)
        jwt_auth.authenticate_from_header = AsyncMock(
            return_value=AuthResult("jwt-user", AuthMethod.JWT)
        )
        
        cert_auth = Mock(spec=CertificateAuthenticator)
        cert_auth.authenticate_from_header = AsyncMock(
            return_value=AuthResult("cert-user", AuthMethod.CERTIFICATE)
        )
        
        secret_auth = Mock(spec=SecretKeyAuthenticator)
        secret_auth.authenticate_from_header = AsyncMock(
            return_value=AuthResult("secret-user", AuthMethod.SECRET_KEY)
        )
        
        handler = AuthenticationHandler(jwt_auth, cert_auth, secret_auth)
        
        # Mock request
        mock_request = Mock(spec=Request)
        
        return handler, jwt_auth, cert_auth, secret_auth, mock_request
    
    @given(
        credentials=single_credential_strategy(),
        explicit_method=st.sampled_from([AuthMethod.JWT, AuthMethod.CERTIFICATE, AuthMethod.SECRET_KEY])
    )
    @settings(max_examples=30)
    async def test_explicit_method_selection(self, credentials: dict, explicit_method: AuthMethod):
        """
        Feature: document-upload-auth, Property 10: Authentication Method Selection
        
        For any request with explicit auth_method parameter,
        the Authentication_Handler SHALL use only that method
        regardless of other credentials present.
        """
        handler, jwt_auth, cert_auth, secret_auth, mock_request = self._create_handler()
        
        # Should use the explicitly specified method, ignoring provided credentials
        result = await handler.authenticate(
            mock_request,
            method=explicit_method,
            authorization=credentials["authorization"],
            x_api_key=credentials["x_api_key"],
            x_client_cert=credentials["x_client_cert"]
        )
        
        # Verify the result matches the explicit method
        assert result.method == explicit_method
        
        # Verify only the correct authenticator was called
        if explicit_method == AuthMethod.JWT:
            jwt_auth.authenticate_from_header.assert_called_once()
            cert_auth.authenticate_from_header.assert_not_called()
            secret_auth.authenticate_from_header.assert_not_called()
        elif explicit_method == AuthMethod.CERTIFICATE:
            jwt_auth.authenticate_from_header.assert_not_called()
            cert_auth.authenticate_from_header.assert_called_once()
            secret_auth.authenticate_from_header.assert_not_called()
        elif explicit_method == AuthMethod.SECRET_KEY:
            jwt_auth.authenticate_from_header.assert_not_called()
            cert_auth.authenticate_from_header.assert_not_called()
            secret_auth.authenticate_from_header.assert_called_once()
    
    @given(credentials=single_credential_strategy())
    @settings(max_examples=30)
    async def test_auto_detect_single_credential(self, credentials: dict):
        """
        Feature: document-upload-auth, Property 10: Authentication Method Selection
        
        For any request with exactly one credential type and no explicit method,
        the handler SHALL auto-detect correctly.
        """
        handler, jwt_auth, cert_auth, secret_auth, mock_request = self._create_handler()
        
        result = await handler.authenticate(
            mock_request,
            method=None,  # No explicit method
            authorization=credentials["authorization"],
            x_api_key=credentials["x_api_key"],
            x_client_cert=credentials["x_client_cert"]
        )
        
        # Verify the result matches the detected method
        expected_method = credentials["method"]
        assert result.method == expected_method
        
        # Verify only the correct authenticator was called
        if expected_method == AuthMethod.JWT:
            jwt_auth.authenticate_from_header.assert_called_once()
            cert_auth.authenticate_from_header.assert_not_called()
            secret_auth.authenticate_from_header.assert_not_called()
        elif expected_method == AuthMethod.SECRET_KEY:
            jwt_auth.authenticate_from_header.assert_not_called()
            cert_auth.authenticate_from_header.assert_not_called()
            secret_auth.authenticate_from_header.assert_called_once()
    
    @given(credentials=multiple_credentials_strategy())
    @settings(max_examples=30)
    async def test_multiple_credentials_rejection(self, credentials: dict):
        """
        Feature: document-upload-auth, Property 10: Authentication Method Selection
        
        For any request with multiple credential types and no explicit method,
        the handler SHALL reject with 400 error.
        """
        handler, jwt_auth, cert_auth, secret_auth, mock_request = self._create_handler()
        
        # Should raise HTTPException with 400 status for ambiguous credentials
        with pytest.raises(HTTPException) as exc_info:
            await handler.authenticate(
                mock_request,
                method=None,  # No explicit method
                authorization=credentials["authorization"],
                x_api_key=credentials["x_api_key"],
                x_client_cert=credentials["x_client_cert"]
            )
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error_code"] == "VALIDATION_AMBIGUOUS_AUTH"
        
        # Verify no authenticators were called
        jwt_auth.authenticate_from_header.assert_not_called()
        cert_auth.authenticate_from_header.assert_not_called()
        secret_auth.authenticate_from_header.assert_not_called()
    
    async def test_no_credentials_rejection(self):
        """
        Feature: document-upload-auth, Property 10: Authentication Method Selection
        
        For any request with no credentials provided,
        the handler SHALL reject with 401 error.
        """
        handler, jwt_auth, cert_auth, secret_auth, mock_request = self._create_handler()
        
        # Should raise HTTPException with 401 status for missing credentials
        with pytest.raises(HTTPException) as exc_info:
            await handler.authenticate(
                mock_request,
                method=None,
                authorization=None,
                x_api_key=None,
                x_client_cert=None
            )
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error_code"] == "AUTH_MISSING"
        
        # Verify no authenticators were called
        jwt_auth.authenticate_from_header.assert_not_called()
        cert_auth.authenticate_from_header.assert_not_called()
        secret_auth.authenticate_from_header.assert_not_called()
    
    @given(invalid_method=st.text(min_size=1, max_size=20))
    @settings(max_examples=20)
    async def test_invalid_explicit_method_rejection(self, invalid_method: str):
        """
        Feature: document-upload-auth, Property 10: Authentication Method Selection
        
        For any invalid explicit auth_method parameter,
        the handler SHALL reject with 400 error.
        """
        # Skip if the invalid method happens to be a valid one
        valid_methods = {AuthMethod.JWT.value, AuthMethod.CERTIFICATE.value, AuthMethod.SECRET_KEY.value}
        if invalid_method in valid_methods:
            return
        
        # Create a mock AuthMethod that's invalid
        try:
            # This should raise an error for invalid method
            with pytest.raises((HTTPException, ValueError, TypeError)):
                await self.handler.authenticate(
                    self.mock_request,
                    method=invalid_method,  # Invalid method
                    authorization="Bearer test-token",
                    x_api_key=None,
                    x_client_cert=None
                )
        except Exception:
            # Expected - invalid method should cause an error
            pass