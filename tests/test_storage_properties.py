"""
Property-based tests for storage service.

Feature: document-upload-auth, Properties 11-12: Storage Service
Validates: Requirements 6.3, 6.4, 6.5
"""
import pytest
from hypothesis import given, strategies as st, settings
from fastapi import HTTPException
from unittest.mock import Mock, AsyncMock, patch
import string
import os

from app.storage.storage_service import StorageService


# Mock UploadFile for testing
class MockUploadFile:
    def __init__(self, filename: str, content: bytes = b"test content", content_type: str = "text/plain"):
        self.filename = filename
        self.content = content
        self.content_type = content_type
    
    async def read(self) -> bytes:
        return self.content


# Strategies for generating test data
@st.composite
def filename_strategy(draw):
    """Generate valid filenames with extensions."""
    base_name = draw(st.text(
        alphabet=string.ascii_letters + string.digits + '_-',
        min_size=1,
        max_size=20
    ))
    extension = draw(st.sampled_from(['.txt', '.pdf', '.jpg', '.doc', '.docx', '.hl7', '.fhir']))
    return base_name + extension


@st.composite
def user_id_strategy(draw):
    """Generate user IDs."""
    return draw(st.text(
        alphabet=string.ascii_letters + string.digits + '_-@.',
        min_size=1,
        max_size=50
    ))


class TestStorageServiceProperties:
    """
    Properties 11-12: Storage Service
    
    Property 11: Storage Unique Naming
    Property 12: Storage Metadata and Response
    
    Validates: Requirements 6.3, 6.4, 6.5
    """
    
    def setup_method(self):
        """Set up test fixtures."""
        self.bucket_name = "test-bucket"
    
    def _create_mock_storage_service(self):
        """Create a storage service with mocked GCS client."""
        service = StorageService(self.bucket_name)
        
        # Mock the GCS client and bucket
        mock_client = Mock()
        mock_bucket = Mock()
        mock_blob = Mock()
        
        # Configure mocks
        mock_bucket.blob.return_value = mock_blob
        mock_blob.upload_from_string = Mock()
        mock_blob.metadata = {}
        
        service.client = mock_client
        service.bucket = mock_bucket
        
        return service, mock_bucket, mock_blob
    
    @given(
        filename1=filename_strategy(),
        filename2=filename_strategy(),
        user_id=user_id_strategy()
    )
    @settings(max_examples=10, deadline=None)
    async def test_unique_object_naming(self, filename1: str, filename2: str, user_id: str):
        """
        Feature: document-upload-auth, Property 11: Storage Unique Naming
        
        For any two uploads with the same original filename,
        the Storage_Service SHALL generate different object names.
        """
        service, mock_bucket, mock_blob = self._create_mock_storage_service()
        
        # Use the same filename for both uploads
        same_filename = filename1
        file1 = MockUploadFile(same_filename)
        file2 = MockUploadFile(same_filename)
        
        # Track the generated object names
        generated_names = []
        
        def capture_blob_name(name):
            generated_names.append(name)
            return mock_blob
        
        mock_bucket.blob.side_effect = capture_blob_name
        
        # Upload both files
        await service.upload(file1, user_id)
        await service.upload(file2, user_id)
        
        # Verify different object names were generated
        assert len(generated_names) == 2
        assert generated_names[0] != generated_names[1]
        
        # Verify both preserve the original extension
        original_ext = os.path.splitext(same_filename)[1]
        for name in generated_names:
            assert name.endswith(original_ext)
    
    @given(
        filename=filename_strategy(),
        user_id=user_id_strategy(),
        content=st.binary(min_size=1, max_size=100)
    )
    @settings(max_examples=10, deadline=None)
    async def test_metadata_preservation_and_response(self, filename: str, user_id: str, content: bytes):
        """
        Feature: document-upload-auth, Property 12: Storage Metadata and Response
        
        For any successful upload, the Storage_Service SHALL store the original
        filename as metadata AND return the GCS object path in the response.
        """
        service, mock_bucket, mock_blob = self._create_mock_storage_service()
        
        file = MockUploadFile(filename, content)
        
        # Track metadata and object name
        captured_metadata = {}
        captured_object_name = None
        
        def capture_blob_creation(name):
            nonlocal captured_object_name
            captured_object_name = name
            return mock_blob
        
        def capture_metadata(metadata):
            captured_metadata.update(metadata)
        
        mock_bucket.blob.side_effect = capture_blob_creation
        
        # Mock metadata assignment
        type(mock_blob).metadata = property(
            lambda self: captured_metadata,
            lambda self, value: capture_metadata(value)
        )
        
        # Upload file
        result_path = await service.upload(file, user_id)
        
        # Verify metadata contains original filename
        assert "original_filename" in captured_metadata
        assert captured_metadata["original_filename"] == filename
        assert captured_metadata["uploaded_by"] == user_id
        
        # Verify response contains GCS object path
        assert result_path.startswith(f"gs://{self.bucket_name}/")
        assert captured_object_name in result_path
        
        # Verify upload was called with correct content
        mock_blob.upload_from_string.assert_called_once_with(
            content,
            content_type=file.content_type
        )
    
    @given(
        filename=filename_strategy(),
        user_id=user_id_strategy()
    )
    @settings(max_examples=10, deadline=None)
    async def test_extension_preservation(self, filename: str, user_id: str):
        """
        Feature: document-upload-auth, Property 11: Storage Unique Naming
        
        For any filename with an extension, the generated object name
        SHALL preserve the original extension.
        """
        service = StorageService(self.bucket_name)
        
        # Test the _generate_object_name method directly
        generated_name = service._generate_object_name(filename)
        
        # Extract extensions
        original_ext = os.path.splitext(filename)[1]
        generated_ext = os.path.splitext(generated_name)[1]
        
        # Verify extension is preserved
        assert generated_ext == original_ext
        
        # Verify the name is different from original (contains UUID)
        assert generated_name != filename
        assert len(generated_name) > len(original_ext)  # Should have UUID + extension
    
    @given(user_id=user_id_strategy())
    @settings(max_examples=5, deadline=None)
    async def test_storage_connection_failure(self, user_id: str):
        """
        Feature: document-upload-auth, Property 12: Storage Metadata and Response
        
        For any upload when GCS connection fails,
        the Storage_Service SHALL return a 500 error with appropriate details.
        """
        # Create service with no GCS connection
        service = StorageService(self.bucket_name)
        service.client = None
        service.bucket = None
        
        file = MockUploadFile("test.txt")
        
        # Should raise HTTPException with 500 status
        with pytest.raises(HTTPException) as exc_info:
            await service.upload(file, user_id)
        
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail["error_code"] == "STORAGE_CONNECTION_FAILED"
    
    @given(
        filename=filename_strategy(),
        user_id=user_id_strategy()
    )
    @settings(max_examples=5, deadline=None)
    async def test_upload_failure_handling(self, filename: str, user_id: str):
        """
        Feature: document-upload-auth, Property 12: Storage Metadata and Response
        
        For any upload that fails during GCS operation,
        the Storage_Service SHALL return a 500 error with appropriate details.
        """
        service, mock_bucket, mock_blob = self._create_mock_storage_service()
        
        # Make upload_from_string raise an exception
        mock_blob.upload_from_string.side_effect = Exception("GCS upload failed")
        
        file = MockUploadFile(filename)
        
        # Should raise HTTPException with 500 status
        with pytest.raises(HTTPException) as exc_info:
            await service.upload(file, user_id)
        
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail["error_code"] == "STORAGE_UPLOAD_FAILED"
    
    @given(
        filenames=st.lists(filename_strategy(), min_size=2, max_size=5, unique=False),
        user_id=user_id_strategy()
    )
    @settings(max_examples=5, deadline=None)
    async def test_multiple_uploads_unique_names(self, filenames: list, user_id: str):
        """
        Feature: document-upload-auth, Property 11: Storage Unique Naming
        
        For any sequence of uploads (even with duplicate filenames),
        the Storage_Service SHALL generate unique object names for each.
        """
        service, mock_bucket, mock_blob = self._create_mock_storage_service()
        
        # Track all generated object names
        generated_names = []
        
        def capture_blob_name(name):
            generated_names.append(name)
            return mock_blob
        
        mock_bucket.blob.side_effect = capture_blob_name
        
        # Upload all files
        for filename in filenames:
            file = MockUploadFile(filename)
            await service.upload(file, user_id)
        
        # Verify all generated names are unique
        assert len(generated_names) == len(filenames)
        assert len(set(generated_names)) == len(generated_names)  # All unique
        
        # Verify extensions are preserved for each
        for i, filename in enumerate(filenames):
            original_ext = os.path.splitext(filename)[1]
            generated_ext = os.path.splitext(generated_names[i])[1]
            assert generated_ext == original_ext