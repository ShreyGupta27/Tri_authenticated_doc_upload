from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError
from fastapi import UploadFile, HTTPException
from uuid import uuid4
import os
from typing import Optional


class StorageService:
    """Handles file uploads to Google Cloud Storage."""
    
    def __init__(self, bucket_name: str):
        """
        Initialize storage service.
        
        Args:
            bucket_name: Name of the GCS bucket to upload to
        """
        self.bucket_name = bucket_name
        try:
            self.client = storage.Client()
            self.bucket = self.client.bucket(bucket_name)
        except Exception as e:
            # Allow initialization to succeed even if GCS is not available
            # This enables testing and development without GCS credentials
            self.client = None
            self.bucket = None
    
    async def upload(self, file: UploadFile, user_id: str) -> str:
        """
        Upload file to GCS with unique name.
        
        Args:
            file: The uploaded file to store
            user_id: ID of the user uploading the file
            
        Returns:
            The GCS object path (gs://bucket/object_name)
            
        Raises:
            HTTPException: 500 error for storage failures
        """
        if not self.client or not self.bucket:
            raise HTTPException(
                status_code=500,
                detail={
                    "error_code": "STORAGE_CONNECTION_FAILED",
                    "message": "Cannot connect to Google Cloud Storage"
                }
            )
        
        try:
            # Generate unique object name
            object_name = self._generate_object_name(file.filename or "unknown")
            
            # Create blob in GCS
            blob = self.bucket.blob(object_name)
            
            # Set metadata
            blob.metadata = {
                "original_filename": file.filename or "unknown",
                "uploaded_by": user_id,
                "content_type": file.content_type or "application/octet-stream"
            }
            
            # Read file content
            file_content = await file.read()
            
            # Upload to GCS
            blob.upload_from_string(
                file_content,
                content_type=file.content_type or "application/octet-stream"
            )
            
            # Return GCS path
            return f"gs://{self.bucket_name}/{object_name}"
            
        except GoogleCloudError as e:
            raise HTTPException(
                status_code=500,
                detail={
                    "error_code": "STORAGE_UPLOAD_FAILED",
                    "message": f"Failed to upload to Google Cloud Storage: {str(e)}"
                }
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail={
                    "error_code": "STORAGE_UPLOAD_FAILED",
                    "message": f"Upload failed: {str(e)}"
                }
            )
    
    def _generate_object_name(self, original_filename: str) -> str:
        """
        Generate unique object name preserving extension.
        
        Args:
            original_filename: Original filename from upload
            
        Returns:
            Unique object name with preserved extension
        """
        # Extract extension
        _, ext = os.path.splitext(original_filename)
        
        # Generate unique name with UUID
        unique_id = str(uuid4())
        
        # Combine with extension
        return f"{unique_id}{ext}"
    
    def get_download_url(self, object_path: str, expiration_minutes: int = 60) -> str:
        """
        Generate a signed URL for downloading a file.
        
        Args:
            object_path: GCS object path (gs://bucket/object_name)
            expiration_minutes: URL expiration time in minutes
            
        Returns:
            Signed download URL
            
        Raises:
            HTTPException: 500 error for storage failures
        """
        if not self.client or not self.bucket:
            raise HTTPException(
                status_code=500,
                detail={
                    "error_code": "STORAGE_CONNECTION_FAILED",
                    "message": "Cannot connect to Google Cloud Storage"
                }
            )
        
        try:
            # Extract object name from path
            if object_path.startswith(f"gs://{self.bucket_name}/"):
                object_name = object_path[len(f"gs://{self.bucket_name}/"):]
            else:
                object_name = object_path
            
            blob = self.bucket.blob(object_name)
            
            # Generate signed URL
            from datetime import timedelta
            url = blob.generate_signed_url(
                expiration=timedelta(minutes=expiration_minutes),
                method="GET"
            )
            
            return url
            
        except GoogleCloudError as e:
            raise HTTPException(
                status_code=500,
                detail={
                    "error_code": "STORAGE_CONNECTION_FAILED",
                    "message": f"Failed to generate download URL: {str(e)}"
                }
            )
    
    def delete_file(self, object_path: str) -> bool:
        """
        Delete a file from GCS.
        
        Args:
            object_path: GCS object path (gs://bucket/object_name)
            
        Returns:
            True if file was deleted, False if file didn't exist
            
        Raises:
            HTTPException: 500 error for storage failures
        """
        if not self.client or not self.bucket:
            raise HTTPException(
                status_code=500,
                detail={
                    "error_code": "STORAGE_CONNECTION_FAILED",
                    "message": "Cannot connect to Google Cloud Storage"
                }
            )
        
        try:
            # Extract object name from path
            if object_path.startswith(f"gs://{self.bucket_name}/"):
                object_name = object_path[len(f"gs://{self.bucket_name}/"):]
            else:
                object_name = object_path
            
            blob = self.bucket.blob(object_name)
            
            if blob.exists():
                blob.delete()
                return True
            else:
                return False
                
        except GoogleCloudError as e:
            raise HTTPException(
                status_code=500,
                detail={
                    "error_code": "STORAGE_UPLOAD_FAILED",
                    "message": f"Failed to delete file: {str(e)}"
                }
            )
    
    def get_file_metadata(self, object_path: str) -> Optional[dict]:
        """
        Get metadata for a stored file.
        
        Args:
            object_path: GCS object path (gs://bucket/object_name)
            
        Returns:
            Dictionary with file metadata or None if file doesn't exist
            
        Raises:
            HTTPException: 500 error for storage failures
        """
        if not self.client or not self.bucket:
            raise HTTPException(
                status_code=500,
                detail={
                    "error_code": "STORAGE_CONNECTION_FAILED",
                    "message": "Cannot connect to Google Cloud Storage"
                }
            )
        
        try:
            # Extract object name from path
            if object_path.startswith(f"gs://{self.bucket_name}/"):
                object_name = object_path[len(f"gs://{self.bucket_name}/"):]
            else:
                object_name = object_path
            
            blob = self.bucket.blob(object_name)
            
            if blob.exists():
                blob.reload()  # Fetch latest metadata
                return {
                    "name": blob.name,
                    "size": blob.size,
                    "content_type": blob.content_type,
                    "created": blob.time_created.isoformat() if blob.time_created else None,
                    "updated": blob.updated.isoformat() if blob.updated else None,
                    "metadata": blob.metadata or {}
                }
            else:
                return None
                
        except GoogleCloudError as e:
            raise HTTPException(
                status_code=500,
                detail={
                    "error_code": "STORAGE_CONNECTION_FAILED",
                    "message": f"Failed to get file metadata: {str(e)}"
                }
            )