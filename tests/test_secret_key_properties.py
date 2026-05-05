"""
Property-based tests for secret key authentication.

Feature: document-upload-auth, Property 9: Secret Key Authentication
Validates: Requirements 4.1, 4.2
"""
import pytest
from hypothesis import given, strategies as st, settings
from fastapi import HTTPException
import string

from app.auth.secret_key_authenticator import SecretKeyAuthenticator
from app.models import AuthMethod


# Strategies for generating test data
@st.composite
def valid_api_key_mapping_strategy(draw):
    """Generate valid API key mappings."""
    # Generate 1-5 key-value pairs
    num_keys = draw(st.integers(min_value=1, max_value=5))
    
    keys_and_apps = {}
    for _ in range(num_keys):
        # Generate API key
        api_key = draw(st.text(
            alphabet=string.ascii_letters + string.digits + '-_',
            min_size=8,
            max_size=32
        ))
        
        # Generate app name
        app_name = draw(st.text(
            alphabet=string.ascii_letters + string.digits + '-_',
            min_size=3,
            max_size=20
        ))
        
        keys_and_apps[api_key] = app_name
    
    return keys_and_apps


@st.composite
def invalid_api_key_strategy(draw):
    """Generate API keys that are not in the valid set."""
    return draw(st.text(
        alphabet=string.ascii_letters + string.digits + '-_!@#$%^&*()',
        min_size=1,
        max_size=50
    ))


class TestSecretKeyAuthenticationProperty:
    """
    Property 9: Secret Key Authentication
    
    For any API key in the configured valid_keys set, the Secret_Key_Authenticator
    SHALL return an AuthResult. For any API key NOT in the valid_keys set,
    the Secret_Key_Authenticator SHALL reject with a 401 Unauthorized error.
    
    Validates: Requirements 4.1, 4.2
    """
    
    @given(
        valid_keys=valid_api_key_mapping_strategy(),
        selected_key=st.data()
    )
    @settings(max_examples=50)
    async def test_valid_api_key_authentication(self, valid_keys: dict, selected_key):
        """
        Feature: document-upload-auth, Property 9: Secret Key Authentication
        
        For any API key in the configured valid_keys set,
        the Secret_Key_Authenticator SHALL return an AuthResult with
        user_id matching the app_name.
        """
        # Select one of the valid keys
        api_key = selected_key.draw(st.sampled_from(list(valid_keys.keys())))
        expected_app_name = valid_keys[api_key]
        
        authenticator = SecretKeyAuthenticator(valid_keys)
        
        # Should authenticate successfully
        result = await authenticator.authenticate(api_key)
        
        assert result.user_id == expected_app_name
        assert result.method == AuthMethod.SECRET_KEY
        assert result.metadata["app_name"] == expected_app_name
        assert "api_key" in result.metadata
    
    @given(
        valid_keys=valid_api_key_mapping_strategy(),
        invalid_key=invalid_api_key_strategy()
    )
    @settings(max_examples=50)
    async def test_invalid_api_key_rejection(self, valid_keys: dict, invalid_key: str):
        """
        Feature: document-upload-auth, Property 9: Secret Key Authentication
        
        For any API key NOT in the valid_keys set,
        the Secret_Key_Authenticator SHALL reject with a 401 Unauthorized error.
        """
        # Ensure the invalid key is not in the valid set
        if invalid_key in valid_keys:
            return  # Skip this test case
        
        authenticator = SecretKeyAuthenticator(valid_keys)
        
        # Should raise HTTPException with 401 status
        with pytest.raises(HTTPException) as exc_info:
            await authenticator.authenticate(invalid_key)
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error_code"] == "AUTH_KEY_INVALID"
    
    @given(valid_keys=valid_api_key_mapping_strategy())
    @settings(max_examples=30)
    async def test_empty_api_key_rejection(self, valid_keys: dict):
        """
        Feature: document-upload-auth, Property 9: Secret Key Authentication
        
        For empty or None API keys,
        the Secret_Key_Authenticator SHALL reject with a 401 Unauthorized error.
        """
        authenticator = SecretKeyAuthenticator(valid_keys)
        
        # Test empty string
        with pytest.raises(HTTPException) as exc_info:
            await authenticator.authenticate("")
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error_code"] == "AUTH_KEY_INVALID"
    
    @given(
        valid_keys=valid_api_key_mapping_strategy(),
        selected_key=st.data()
    )
    @settings(max_examples=30)
    async def test_header_authentication(self, valid_keys: dict, selected_key):
        """
        Feature: document-upload-auth, Property 9: Secret Key Authentication
        
        For any valid API key provided in X-API-Key header,
        the Secret_Key_Authenticator SHALL authenticate successfully.
        """
        # Select one of the valid keys
        api_key = selected_key.draw(st.sampled_from(list(valid_keys.keys())))
        expected_app_name = valid_keys[api_key]
        
        authenticator = SecretKeyAuthenticator(valid_keys)
        
        # Test with header (including whitespace)
        header_value = f"  {api_key}  "
        result = await authenticator.authenticate_from_header(header_value)
        
        assert result.user_id == expected_app_name
        assert result.method == AuthMethod.SECRET_KEY
    
    @given(valid_keys=valid_api_key_mapping_strategy())
    @settings(max_examples=20)
    async def test_missing_header_rejection(self, valid_keys: dict):
        """
        Feature: document-upload-auth, Property 9: Secret Key Authentication
        
        For missing X-API-Key header,
        the Secret_Key_Authenticator SHALL reject with a 401 Unauthorized error.
        """
        authenticator = SecretKeyAuthenticator(valid_keys)
        
        # Test None header
        with pytest.raises(HTTPException) as exc_info:
            await authenticator.authenticate_from_header(None)
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error_code"] == "AUTH_MISSING"
        
        # Test empty header
        with pytest.raises(HTTPException) as exc_info:
            await authenticator.authenticate_from_header("")
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error_code"] == "AUTH_MISSING"
    
    @given(
        initial_keys=valid_api_key_mapping_strategy(),
        new_key=st.text(
            alphabet=string.ascii_letters + string.digits + '-_',
            min_size=8,
            max_size=32
        ),
        new_app=st.text(
            alphabet=string.ascii_letters + string.digits + '-_',
            min_size=3,
            max_size=20
        )
    )
    @settings(max_examples=20)
    async def test_dynamic_key_management(self, initial_keys: dict, new_key: str, new_app: str):
        """
        Feature: document-upload-auth, Property 9: Secret Key Authentication
        
        For dynamically added keys, the Secret_Key_Authenticator SHALL
        authenticate them successfully. For removed keys, it SHALL reject them.
        """
        # Ensure new key is not in initial set
        if new_key in initial_keys:
            return  # Skip this test case
        
        authenticator = SecretKeyAuthenticator(initial_keys)
        
        # Initially, new key should be rejected
        with pytest.raises(HTTPException):
            await authenticator.authenticate(new_key)
        
        # Add the new key
        authenticator.add_key(new_key, new_app)
        
        # Now it should authenticate successfully
        result = await authenticator.authenticate(new_key)
        assert result.user_id == new_app
        
        # Remove the key
        removed = authenticator.remove_key(new_key)
        assert removed is True
        
        # Should be rejected again
        with pytest.raises(HTTPException):
            await authenticator.authenticate(new_key)