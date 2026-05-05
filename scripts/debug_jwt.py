#!/usr/bin/env python3
"""
Debug JWT tokens to verify they're working correctly.
"""
import jwt
import requests
from datetime import datetime, timedelta

def create_and_test_jwt():
    """Create a JWT and test it directly."""
    # Create JWT
    payload = {
        "user_id": "test-user-123",
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    secret = "test-secret-key-for-development-only"
    token = jwt.encode(payload, secret, algorithm="HS256")
    
    print("🔑 Generated JWT Token:")
    print(f"Token: {token}")
    print()
    
    # Verify the token can be decoded
    try:
        decoded = jwt.decode(token, secret, algorithms=["HS256"])
        print("✅ Token verification successful:")
        print(f"User ID: {decoded['user_id']}")
        print(f"Expires: {datetime.fromtimestamp(decoded['exp'])}")
        print()
    except Exception as e:
        print(f"❌ Token verification failed: {e}")
        return None
    
    # Test with API
    print("🌐 Testing with API...")
    try:
        # Create a test file
        import io
        test_file = io.BytesIO(b"Test PDF content")
        files = {"file": ("test.pdf", test_file, "application/pdf")}
        
        # Test with Bearer format
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post("http://localhost:8000/upload", files=files, headers=headers)
        
        print(f"API Response: {response.status_code}")
        print(f"Response body: {response.json()}")
        
        if response.status_code == 500 and "STORAGE_CONNECTION_FAILED" in response.text:
            print("✅ JWT authentication is working! (Storage error is expected)")
        elif response.status_code == 401:
            print("❌ JWT authentication failed")
        else:
            print(f"🤔 Unexpected response: {response.status_code}")
            
    except Exception as e:
        print(f"❌ API test failed: {e}")
    
    return token

def test_manual_entry():
    """Show exactly how to enter the token in Swagger UI."""
    token = create_and_test_jwt()
    if token:
        print("\n" + "="*60)
        print("📋 COPY THIS FOR SWAGGER UI:")
        print("="*60)
        print("Method 1 - Use Authorize button (recommended):")
        print(f"Just paste this token: {token}")
        print()
        print("Method 2 - Use authorization field:")
        print(f"Enter exactly: Bearer {token}")
        print("="*60)

if __name__ == "__main__":
    test_manual_entry()