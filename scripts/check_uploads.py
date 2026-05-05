#!/usr/bin/env python3
"""
Script to check uploaded files in Google Cloud Storage.
"""
from google.cloud import storage
from app.config import settings
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def list_uploaded_files():
    """List all files in the GCS bucket."""
    try:
        # Initialize the client - it will use GOOGLE_APPLICATION_CREDENTIALS env var
        client = storage.Client()
        bucket = client.bucket(settings.gcs_bucket_name)
        
        print(f"📁 Files in bucket: {settings.gcs_bucket_name}")
        print("=" * 80)
        
        # List all blobs (files) in the bucket
        blobs = list(bucket.list_blobs())
        
        if not blobs:
            print("❌ No files found in bucket")
            return
        
        # Sort by creation time (newest first)
        blobs.sort(key=lambda x: x.time_created, reverse=True)
        
        for i, blob in enumerate(blobs, 1):
            # Format file size
            size_mb = blob.size / (1024 * 1024) if blob.size else 0
            
            # Format timestamp
            created = blob.time_created.strftime("%Y-%m-%d %H:%M:%S") if blob.time_created else "Unknown"
            
            print(f"{i:2d}. {blob.name}")
            print(f"    📊 Size: {size_mb:.2f} MB")
            print(f"    🕒 Created: {created}")
            print(f"    🔗 URL: gs://{settings.gcs_bucket_name}/{blob.name}")
            print("-" * 80)
        
        print(f"\n📈 Total files: {len(blobs)}")
        
    except Exception as e:
        logger.error(f"❌ Failed to list files: {e}")


def download_file(filename: str, local_path: str = None):
    """Download a specific file from GCS."""
    try:
        client = storage.Client()
        bucket = client.bucket(settings.gcs_bucket_name)
        blob = bucket.blob(filename)
        
        if not blob.exists():
            print(f"❌ File {filename} not found in bucket")
            return
        
        # Use filename if no local path specified
        if not local_path:
            local_path = f"downloaded_{filename}"
        
        blob.download_to_filename(local_path)
        print(f"✅ Downloaded {filename} to {local_path}")
        
    except Exception as e:
        logger.error(f"❌ Failed to download file: {e}")


def get_file_info(filename: str):
    """Get detailed info about a specific file."""
    try:
        client = storage.Client()
        bucket = client.bucket(settings.gcs_bucket_name)
        blob = bucket.blob(filename)
        
        if not blob.exists():
            print(f"❌ File {filename} not found in bucket")
            return
        
        # Reload to get latest metadata
        blob.reload()
        
        print(f"📄 File Information: {filename}")
        print("=" * 50)
        print(f"Size: {blob.size / (1024 * 1024):.2f} MB ({blob.size} bytes)")
        print(f"Content Type: {blob.content_type}")
        print(f"Created: {blob.time_created}")
        print(f"Updated: {blob.updated}")
        print(f"MD5 Hash: {blob.md5_hash}")
        print(f"CRC32C: {blob.crc32c}")
        print(f"Public URL: gs://{settings.gcs_bucket_name}/{filename}")
        
        if blob.metadata:
            print(f"Metadata: {blob.metadata}")
        
    except Exception as e:
        logger.error(f"❌ Failed to get file info: {e}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("""
🔍 GOOGLE CLOUD STORAGE FILE CHECKER
===================================

Commands:
    python check_uploads.py list                    # List all files
    python check_uploads.py info <filename>         # Get file details
    python check_uploads.py download <filename>     # Download file
    
Examples:
    python check_uploads.py list
    python check_uploads.py info 6e056d36-e60b-4ac8-827a-350dee89929b.pdf
    python check_uploads.py download 6e056d36-e60b-4ac8-827a-350dee89929b.pdf
        """)
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "list":
        list_uploaded_files()
    elif command == "info" and len(sys.argv) > 2:
        get_file_info(sys.argv[2])
    elif command == "download" and len(sys.argv) > 2:
        local_path = sys.argv[3] if len(sys.argv) > 3 else None
        download_file(sys.argv[2], local_path)
    else:
        print("❌ Invalid command or missing filename")