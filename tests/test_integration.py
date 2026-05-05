"""
Integration tests for the document upload endpoint.

Tests the full flow with each authentication method and error scenarios.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
import io
import jwt
from datetime import datetime, timedelta

from app.main import app
from app.config import Settings


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_storage_service():
    """Mock storage service to avoid actual GCS calls."""
    with patch('app.main.storage_service') as mock:
        mock.upload = AsyncMock(return_value="gs://test-bucket/unique-file-id.pdf")
        yield mock


@pytest.fixture
def valid_jwt_token():
    """Create a valid JWT token for testing."""
    settings = Settings()
    payload = {
        "user_id": "test-user",
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


@pytest.fixture
def expired_jwt_token():
    """Create an expired JWT token for testing."""
    settings = Settings()
    payload = {
        "user_id": "test-user",
        "exp": datetime.utcnow() - timedelta(hours=1)
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


@pytest.fixture
def test_file():
    """Create a test file for upload."""
    file_content = b"Test PDF content"
    return ("test.pdf", io.BytesIO(file_content), "application/pdf")


class TestUploadEndpoint:
    """Integration tests for the upload endpoint."""

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy", "service": "document-upload"}

    def test_upload_with_jwt_success(self, client, mock_storage_service, valid_jwt_token, test_file):
        """Test successful upload with JWT authentication."""
        response = client.post(
            "/upload",
            files={"file": test_file},
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
            params={"auth_method": "jwt"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["object_path"] == "gs://test-bucket/unique-file-id.pdf"
        assert data["filename"] == "test.pdf"
        
        # Verify storage service was called
        mock_storage_service.upload.assert_called_once()

    def test_upload_with_secret_key_success(self, client, mock_storage_service, test_file):
        """Test successful upload with secret key authentication."""
        response = client.post(
            "/upload",
            files={"file": test_file},
            headers={"X-API-Key": "test-key-1"},
            params={"auth_method": "secret_key"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["object_path"] == "gs://test-bucket/unique-file-id.pdf"
        assert data["filename"] == "test.pdf"

    def test_upload_with_certificate_success(self, client, mock_storage_service, test_file):
        """Test successful upload with certificate authentication."""
        # Mock certificate validation to return success
        with patch('app.auth.certificate_authenticator.CertificateAuthenticator.authenticate') as mock_auth:
            from app.models import AuthResult, AuthMethod
            mock_auth.return_value = AuthResult("cert-user", AuthMethod.CERTIFICATE)
            
            response = client.post(
                "/upload",
                files={"file": test_file},
                headers={"X-Client-Cert": "-----BEGIN CERTIFICATE-----\nMOCK_CERT\n-----END CERTIFICATE-----"},
                params={"auth_method": "certificate"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"

    def test_upload_auto_detect_jwt(self, client, mock_storage_service, valid_jwt_token, test_file):
        """Test upload with auto-detection of JWT method."""
        response = client.post(
            "/upload",
            files={"file": test_file},
            headers={"Authorization": f"Bearer {valid_jwt_token}"}
            # No explicit auth_method parameter
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_upload_auto_detect_secret_key(self, client, mock_storage_service, test_file):
        """Test upload with auto-detection of secret key method."""
        response = client.post(
            "/upload",
            files={"file": test_file},
            headers={"X-API-Key": "test-key-1"}
            # No explicit auth_method parameter
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_upload_invalid_file_extension(self, client, valid_jwt_token):
        """Test upload with invalid file extension."""
        invalid_file = ("test.exe", io.BytesIO(b"executable content"), "application/octet-stream")
        
        response = client.post(
            "/upload",
            files={"file": invalid_file},
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
            params={"auth_method": "jwt"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "VALIDATION_UNSUPPORTED_FORMAT"

    def test_upload_expired_jwt_token(self, client, expired_jwt_token, test_file):
        """Test upload with expired JWT token."""
        response = client.post(
            "/upload",
            files={"file": test_file},
            headers={"Authorization": f"Bearer {expired_jwt_token}"},
            params={"auth_method": "jwt"}
        )
        
        assert response.status_code == 401
        data = response.json()
        assert data["error_code"] == "AUTH_TOKEN_EXPIRED"

    def test_upload_invalid_jwt_token(self, client, test_file):
        """Test upload with invalid JWT token."""
        response = client.post(
            "/upload",
            files={"file": test_file},
            headers={"Authorization": "Bearer invalid-token"},
            params={"auth_method": "jwt"}
        )
        
        assert response.status_code == 401
        data = response.json()
        assert data["error_code"] == "AUTH_TOKEN_INVALID"

    def test_upload_invalid_secret_key(self, client, test_file):
        """Test upload with invalid secret key."""
        response = client.post(
            "/upload",
            files={"file": test_file},
            headers={"X-API-Key": "invalid-key"},
            params={"auth_method": "secret_key"}
        )
        
        assert response.status_code == 401
        data = response.json()
        assert data["error_code"] == "AUTH_KEY_INVALID"

    def test_upload_no_authentication(self, client, test_file):
        """Test upload without any authentication."""
        response = client.post(
            "/upload",
            files={"file": test_file}
        )
        
        assert response.status_code == 401
        data = response.json()
        assert data["error_code"] == "AUTH_MISSING"

    def test_upload_ambiguous_authentication(self, client, valid_jwt_token, test_file):
        """Test upload with multiple authentication methods without explicit selection."""
        response = client.post(
            "/upload",
            files={"file": test_file},
            headers={
                "Authorization": f"Bearer {valid_jwt_token}",
                "X-API-Key": "test-key-1"
            }
            # No explicit auth_method parameter
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "VALIDATION_AMBIGUOUS_AUTH"

    def test_upload_storage_failure(self, client, valid_jwt_token, test_file):
        """Test upload with storage service failure."""
        with patch('app.main.storage_service') as mock_storage:
            from app.exceptions import StorageException
            mock_storage.upload = AsyncMock(side_effect=StorageException("STORAGE_UPLOAD_FAILED", "Failed to upload to GCS"))
            
            response = client.post(
                "/upload",
                files={"file": test_file},
                headers={"Authorization": f"Bearer {valid_jwt_token}"},
                params={"auth_method": "jwt"}
            )
            
            assert response.status_code == 500
            data = response.json()
            assert data["error_code"] == "STORAGE_UPLOAD_FAILED"

    def test_upload_missing_file(self, client, valid_jwt_token):
        """Test upload without providing a file."""
        response = client.post(
            "/upload",
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
            params={"auth_method": "jwt"}
        )
        
        assert response.status_code == 400  # Our custom validation error handler converts to 400
        data = response.json()
        assert "details" in data

    def test_upload_all_supported_formats(self, client, mock_storage_service, valid_jwt_token):
        """Test upload with all supported file formats."""
        supported_formats = [
            ("test.hl7", "application/octet-stream"),
            ("test.fhir", "application/json"),
            ("test.jpg", "image/jpeg"),
            ("test.jpeg", "image/jpeg"),
            ("test.bmp", "image/bmp"),
            ("test.pdf", "application/pdf"),
            ("test.doc", "application/msword"),
            ("test.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        ]
        
        for filename, content_type in supported_formats:
            test_file = (filename, io.BytesIO(b"test content"), content_type)
            
            response = client.post(
                "/upload",
                files={"file": test_file},
                headers={"Authorization": f"Bearer {valid_jwt_token}"},
                params={"auth_method": "jwt"}
            )
            
            assert response.status_code == 200, f"Failed for {filename}"
            data = response.json()
            assert data["status"] == "success"
            assert data["filename"] == filename

    def test_error_response_format(self, client, test_file):
        """Test that all error responses follow the standard format."""
        # Test authentication error
        response = client.post(
            "/upload",
            files={"file": test_file},
            headers={"Authorization": "Bearer invalid-token"},
            params={"auth_method": "jwt"}
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "error_code" in data
        assert "message" in data
        assert isinstance(data["error_code"], str)
        assert isinstance(data["message"], str)
        
        # Ensure no sensitive information is exposed
        assert "secret" not in str(data).lower()
        assert "password" not in str(data).lower()
        assert "traceback" not in str(data).lower()