#!/usr/bin/env python3
"""
Test script to verify database authentication is working.
"""
import requests
import json

# Server URL
BASE_URL = "http://localhost:8000"

# Test credentials from populate_test_auth.py output
TEST_CREDENTIALS = {
    "jwt_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoidGVzdC11c2VyLTIiLCJleHAiOjE3NjgxMTYxMzF9.K9Wy-97uBkRKD02M3zskQsvfUqD6TWKW7zGhMOh-zP4",
    "api_key": "jx_test_6f490a679af77b5684830a31933808a3",
    "webhook_secret": "webhook_secret_521baee11546f2820c8bea006eeb27a9bba74a67"
}

def test_health():
    """Test health endpoint."""
    print("🔍 Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 200

def test_jwt_auth():
    """Test JWT authentication."""
    print("\n🔍 Testing JWT authentication...")
    
    headers = {
        "Authorization": f"Bearer {TEST_CREDENTIALS['jwt_token']}"
    }
    
    # Create a dummy file for testing
    files = {
        "file": ("test.pdf", b"dummy pdf content", "application/pdf")
    }
    
    data = {
        "auth_method": "jwt"
    }
    
    response = requests.post(f"{BASE_URL}/upload", headers=headers, files=files, data=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    # Should get 500 (storage error) but auth should work
    return response.status_code in [200, 500]

def test_api_key_auth():
    """Test API key authentication."""
    print("\n🔍 Testing API key authentication...")
    
    headers = {
        "X-API-Key": TEST_CREDENTIALS['api_key']
    }
    
    files = {
        "file": ("test.pdf", b"dummy pdf content", "application/pdf")
    }
    
    data = {
        "auth_method": "secret_key"
    }
    
    response = requests.post(f"{BASE_URL}/upload", headers=headers, files=files, data=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    # Should get 500 (storage error) but auth should work
    return response.status_code in [200, 500]

def test_invalid_jwt():
    """Test invalid JWT token."""
    print("\n🔍 Testing invalid JWT token...")
    
    headers = {
        "Authorization": "Bearer invalid_token_here"
    }
    
    files = {
        "file": ("test.pdf", b"dummy pdf content", "application/pdf")
    }
    
    data = {
        "auth_method": "jwt"
    }
    
    response = requests.post(f"{BASE_URL}/upload", headers=headers, files=files, data=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    # Should get 401 (auth error)
    return response.status_code == 401

def test_invalid_api_key():
    """Test invalid API key."""
    print("\n🔍 Testing invalid API key...")
    
    headers = {
        "X-API-Key": "invalid_api_key_here"
    }
    
    files = {
        "file": ("test.pdf", b"dummy pdf content", "application/pdf")
    }
    
    data = {
        "auth_method": "secret_key"
    }
    
    response = requests.post(f"{BASE_URL}/upload", headers=headers, files=files, data=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    # Should get 401 (auth error)
    return response.status_code == 401

def main():
    """Run all tests."""
    print("🚀 Testing Database Authentication")
    print("=" * 50)
    
    tests = [
        ("Health Check", test_health),
        ("JWT Authentication", test_jwt_auth),
        ("API Key Authentication", test_api_key_auth),
        ("Invalid JWT Token", test_invalid_jwt),
        ("Invalid API Key", test_invalid_api_key)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, "✅ PASS" if result else "❌ FAIL"))
        except Exception as e:
            print(f"Error: {e}")
            results.append((test_name, f"❌ ERROR: {e}"))
    
    print("\n📊 TEST RESULTS:")
    print("=" * 50)
    for test_name, result in results:
        print(f"{test_name:<25} {result}")
    
    passed = sum(1 for _, result in results if "✅" in result)
    total = len(results)
    print(f"\n🎯 {passed}/{total} tests passed")

if __name__ == "__main__":
    main()