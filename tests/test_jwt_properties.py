"""
Property-based tests for JWT authentication.

Feature: document-upload-auth, Properties 2-5: JWT Authentication
Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5
"""
import pytest
from hypothesis import given, strategies as st, settings
from fastapi import HTTPException
import jwt
from datetime import datetime, timezone, timedelta
import string
import base64
import json

from app.auth.jwt_authenticator import JWTAuthenticator
from app.models import AuthMethod


# Test secret key
TEST_SECRET = "test-secret-key-for-testing"
WRONG_SECRET = "wrong-secret-key"


# Strategies for generating test data
@st.composite
def valid_jwt_payload_strategy(draw):
    """Generate valid JWT payload with user_id."""
    user_id = draw(st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_-@.'),
        min_size=1,
        max_size=50
    ))
    
    # Add expiration time in the future (1 hour from now)
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    
    payload = {
        "user_id": user_id,
        "exp": exp,
        "iat": datetime.now(timezone.utc)
    }
    
    # Sometimes use 'sub' instead of 'user_id'
    if draw(st.booleans()):
        payload["sub"] = payload.pop("user_id")
    
    return payload


@st.composite
def expired_jwt_payload_strategy(draw):
    """Generate JWT payload with expiration in the past."""
    user_id = draw(st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_-@.'),
        min_size=1,
        max_size=50
    ))
    
    # Add expiration time in the past
    exp = datetime.now(timezone.utc) - timedelta(hours=draw(st.integers(min_value=1, max_value=24)))
    
    return {
        "user_id": user_id,
        "exp": exp,
        "iat": datetime.now(timezone.utc) - timedelta(hours=2)
    }


@st.composite
def malformed_token_strategy(draw):
    """Generate malformed JWT tokens."""
    # Various types of malformed tokens
    token_type = draw(st.sampled_from([
        'empty',
        'single_part',
        'two_parts',
        'four_parts',
        'invalid_base64',
        'random_string'
    ]))
    
    if token_type == 'empty':
        return ""
    elif token_type == 'single_part':
        return draw(st.text(alphabet=string.ascii_letters + string.digits, min_size=10, max_size=50))
    elif token_type == 'two_parts':
        part1 = draw(st.text(alphabet=string.ascii_letters + string.digits, min_size=10, max_size=50))
        part2 = draw(st.text(alphabet=string.ascii_letters + string.digits, min_size=10, max_size=50))
        return f"{part1}.{part2}"
    elif token_type == 'four_parts':
        parts = [draw(st.text(alphabet=string.ascii_letters + string.digits, min_size=10, max_size=50)) for _ in range(4)]
        return ".".join(parts)
    elif token_type == 'invalid_base64':
        # Create token with invalid base64 in one of the parts
        header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip('=')
        payload = "invalid-base64-!@#$%"
        signature = draw(st.text(alphabet=string.ascii_letters + string.digits, min_size=10, max_size=50))
        return f"{header}.{payload}.{signature}"
    else:  # random_string
        return draw(st.text(alphabet=string.printable, min_size=10, max_size=100))


class TestJWTAuthenticationProperties:
    """
    Properties 2-5: JWT Authentication
    
    Property 2: JWT Valid Token Authentication
    Property 3: JWT Expired Token Rejection  
    Property 4: JWT Malformed Token Rejection
    Property 5: JWT Invalid Signature Rejection
    
    Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5
    """
    
    @given(payload=valid_jwt_payload_strategy())
    @settings(max_examples=100)
    async def test_valid_token_authentication(self, payload: dict):
        """
        Feature: document-upload-auth, Property 2: JWT Valid Token Authentication
        
        For any valid JWT token (correctly signed, not expired, properly formatted)
        containing a user_id claim, the JWT_Authenticator SHALL return an AuthResult
        with the user_id matching the token's claim.
        """
        authenticator = JWTAuthenticator(TEST_SECRET)
        
        # Create valid token
        token = jwt.encode(payload, TEST_SECRET, algorithm="HS256")
        
        # Should authenticate successfully
        result = await authenticator.authenticate(token)
        
        expected_user_id = payload.get("user_id") or payload.get("sub")
        assert result.user_id == str(expected_user_id)
        assert result.method == AuthMethod.JWT
        assert "claims" in result.metadata
    
    @given(payload=expired_jwt_payload_strategy())
    @settings(max_examples=100)
    async def test_expired_token_rejection(self, payload: dict):
        """
        Feature: document-upload-auth, Property 3: JWT Expired Token Rejection
        
        For any JWT token with an expiration time in the past,
        the JWT_Authenticator SHALL reject with a 401 Unauthorized error.
        """
        authenticator = JWTAuthenticator(TEST_SECRET)
        
        # Create expired token
        token = jwt.encode(payload, TEST_SECRET, algorithm="HS256")
        
        # Should raise HTTPException with 401 status
        with pytest.raises(HTTPException) as exc_info:
            await authenticator.authenticate(token)
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error_code"] == "AUTH_TOKEN_EXPIRED"
    
    @given(malformed_token=malformed_token_strategy())
    @settings(max_examples=100)
    async def test_malformed_token_rejection(self, malformed_token: str):
        """
        Feature: document-upload-auth, Property 4: JWT Malformed Token Rejection
        
        For any string that is not a valid JWT format,
        the JWT_Authenticator SHALL reject with a 401 Unauthorized error.
        """
        authenticator = JWTAuthenticator(TEST_SECRET)
        
        # Should raise HTTPException with 401 status
        with pytest.raises(HTTPException) as exc_info:
            await authenticator.authenticate(malformed_token)
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error_code"] == "AUTH_TOKEN_INVALID"
    
    @given(payload=valid_jwt_payload_strategy())
    @settings(max_examples=100)
    async def test_invalid_signature_rejection(self, payload: dict):
        """
        Feature: document-upload-auth, Property 5: JWT Invalid Signature Rejection
        
        For any JWT token signed with a key different from the configured secret,
        the JWT_Authenticator SHALL reject with a 401 Unauthorized error.
        """
        authenticator = JWTAuthenticator(TEST_SECRET)
        
        # Create token with wrong secret
        token = jwt.encode(payload, WRONG_SECRET, algorithm="HS256")
        
        # Should raise HTTPException with 401 status
        with pytest.raises(HTTPException) as exc_info:
            await authenticator.authenticate(token)
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error_code"] == "AUTH_TOKEN_INVALID"
    
    @given(
        payload=valid_jwt_payload_strategy(),
        header_format=st.sampled_from(['bearer', 'Bearer', 'BEARER'])
    )
    @settings(max_examples=50)
    async def test_bearer_token_extraction(self, payload: dict, header_format: str):
        """
        Feature: document-upload-auth, Property 2: JWT Valid Token Authentication
        
        For any valid Authorization header with Bearer token,
        the JWT_Authenticator SHALL extract and validate the token correctly.
        """
        authenticator = JWTAuthenticator(TEST_SECRET)
        
        # Create valid token
        token = jwt.encode(payload, TEST_SECRET, algorithm="HS256")
        auth_header = f"{header_format} {token}"
        
        # Should authenticate successfully
        result = await authenticator.authenticate_from_header(auth_header)
        
        expected_user_id = payload.get("user_id") or payload.get("sub")
        assert result.user_id == str(expected_user_id)
        assert result.method == AuthMethod.JWT