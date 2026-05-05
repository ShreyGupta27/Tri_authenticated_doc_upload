#!/usr/bin/env python3
"""
Generate JWT tokens for testing the API.
"""
import jwt
from datetime import datetime, timedelta

def generate_test_jwt():
    """Generate a valid JWT token for testing."""
    payload = {
        "user_id": "test-user-123",
        "exp": datetime.utcnow() + timedelta(hours=24)  # Valid for 24 hours
    }
    secret = "test-secret-key-for-development-only"
    token = jwt.encode(payload, secret, algorithm="HS256")
    return token

def generate_expired_jwt():
    """Generate an expired JWT token for testing."""
    payload = {
        "user_id": "test-user-123",
        "exp": datetime.utcnow() - timedelta(hours=1)  # Expired 1 hour ago
    }
    secret = "test-secret-key-for-development-only"
    token = jwt.encode(payload, secret, algorithm="HS256")
    return token

def generate_invalid_jwt():
    """Generate a JWT token with wrong signature for testing."""
    payload = {
        "user_id": "test-user-123",
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    wrong_secret = "wrong-secret-key"
    token = jwt.encode(payload, wrong_secret, algorithm="HS256")
    return token

if __name__ == "__main__":
    print("🔑 JWT Token Generator for API Testing")
    print("=" * 50)
    
    valid_token = generate_test_jwt()
    expired_token = generate_expired_jwt()
    invalid_token = generate_invalid_jwt()
    
    print(f"✅ Valid JWT Token (24h):")
    print(f"Bearer {valid_token}")
    print()
    
    print(f"⏰ Expired JWT Token:")
    print(f"Bearer {expired_token}")
    print()
    
    print(f"❌ Invalid JWT Token (wrong signature):")
    print(f"Bearer {invalid_token}")
    print()
    
    print("📋 Valid API Keys for testing:")
    print("test-key-1")
    print("test-key-2")
    print("demo-key")
    print()
    
    print("🚀 Use these tokens in Swagger UI at: http://localhost:8000/docs")