import pytest
from hypothesis import settings as hypothesis_settings

# Configure Hypothesis for minimum 100 iterations
hypothesis_settings.register_profile("default", max_examples=100)
hypothesis_settings.load_profile("default")


@pytest.fixture
def jwt_secret_key():
    """Test JWT secret key."""
    return "test-secret-key-for-testing"


@pytest.fixture
def valid_api_keys():
    """Test API keys mapping."""
    return {
        "test-key-1": "app1",
        "test-key-2": "app2",
        "test-key-3": "app3"
    }
