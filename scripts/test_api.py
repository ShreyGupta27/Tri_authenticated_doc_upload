#!/usr/bin/env python3
"""
Simple script to test the document upload API.
"""
import requests
import jwt
from datetime import datetime, timedelta
import io

# Server URL
BASE_URL = "http://localhost:8000"

def create_test_jwt():
    """Create a test JWT token."""
    payload = {
        "user_id": "test-user-123",
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, "test-secret-key-for-development-only", algorithm="HS256")

def test_health_check():
    """Test the health check endpoint."""
    print("🔍 Testing health check...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"✅ Health check: {response.status_code} - {response.json()}")
        return True
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_upload_with_jwt():
    """Test file upload with JWT authentication."""
    print("\n🔍 Testing upload with JWT...")
    
    # Create test file
    test_file = io.BytesIO(b"This is a test PDF content")
    files = {"file": ("test.pdf", test_file, "application/pdf")}
    
    # Create JWT token
    token = create_test_jwt()
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.post(f"{BASE_URL}/upload", files=files, headers=headers)
        print(f"✅ JWT Upload: {response.status_code} - {response.json()}")
        return True
    except Exception as e:
        print(f"❌ JWT Upload failed: {e}")
        return False

def test_upload_with_api_key():
    """Test file upload with API key authentication."""
    print("\n🔍 Testing upload with API key...")
    
    # Create test file
    test_file = io.BytesIO(b"This is a test document content")
    files = {"file": ("test.docx", test_file, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    
    headers = {"X-API-Key": "test-key-1"}
    
    try:
        response = requests.post(f"{BASE_URL}/upload", files=files, headers=headers)
        print(f"✅ API Key Upload: {response.status_code} - {response.json()}")
        return True
    except Exception as e:
        print(f"❌ API Key Upload failed: {e}")
        return False

def test_invalid_file_format():
    """Test upload with invalid file format."""
    print("\n🔍 Testing invalid file format...")
    
    # Create test file with invalid extension
    test_file = io.BytesIO(b"This is an executable file")
    files = {"file": ("malware.exe", test_file, "application/octet-stream")}
    
    token = create_test_jwt()
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.post(f"{BASE_URL}/upload", files=files, headers=headers)
        print(f"✅ Invalid format test: {response.status_code} - {response.json()}")
        return True
    except Exception as e:
        print(f"❌ Invalid format test failed: {e}")
        return False

def test_no_authentication():
    """Test upload without authentication."""
    print("\n🔍 Testing upload without authentication...")
    
    # Create test file
    test_file = io.BytesIO(b"This is a test file")
    files = {"file": ("test.jpg", test_file, "image/jpeg")}
    
    try:
        response = requests.post(f"{BASE_URL}/upload", files=files)
        print(f"✅ No auth test: {response.status_code} - {response.json()}")
        return True
    except Exception as e:
        print(f"❌ No auth test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Testing Document Upload API")
    print("=" * 50)
    
    # Test health check first
    if not test_health_check():
        print("\n❌ Server is not running. Please start it first with: python run_server.py")
        return
    
    # Run all tests
    tests = [
        test_upload_with_jwt,
        test_upload_with_api_key,
        test_invalid_file_format,
        test_no_authentication
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n📊 Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All tests passed! The API is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the server logs for details.")

if __name__ == "__main__":
    main()