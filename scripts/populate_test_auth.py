#!/usr/bin/env python3
"""
Script to populate test authentication data in the User table.
Only modifies the three allowed columns: jwtToken, webhookApiKey, webhookSecretKey
"""
import asyncio
import asyncpg
from app.config import settings
import jwt
from datetime import datetime, timedelta, UTC
import secrets
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def populate_test_auth_data():
    """Populate test authentication data for the first few users."""
    try:
        conn = await asyncpg.connect(settings.database_url)
        logger.info("✅ Connected to database")
        
        # Get first 3 users to populate with test data
        users = await conn.fetch('SELECT id FROM "User" ORDER BY id LIMIT 3')
        
        if not users:
            logger.error("❌ No users found in database")
            return
        
        print(f"\n🔑 POPULATING TEST AUTHENTICATION DATA")
        print("=" * 60)
        
        for i, user in enumerate(users, 1):
            user_id = user['id']
            
            # Generate JWT token
            jwt_payload = {
                "user_id": f"test-user-{user_id}",
                "exp": datetime.now(UTC) + timedelta(hours=24)  # 24 hour expiry
            }
            jwt_token = jwt.encode(jwt_payload, settings.jwt_secret_key, algorithm="HS256")
            
            # Generate API key
            api_key = f"jx_test_{secrets.token_hex(16)}"
            
            # Generate webhook secret
            webhook_secret = f"webhook_secret_{secrets.token_hex(20)}"
            
            # Update only the authentication columns (note: exact case-sensitive column names)
            await conn.execute("""
                UPDATE "User" 
                SET "jwtToken" = $1, "webhookApiKey" = $2, "webhookSecretKey" = $3
                WHERE id = $4
            """, jwt_token, api_key, webhook_secret, user_id)
            
            print(f"\n👤 User ID {user_id}:")
            print(f"   JWT Token: {jwt_token}")
            print(f"   API Key: {api_key}")
            print(f"   Webhook Secret: {webhook_secret}")
            
            logger.info(f"✅ Updated authentication data for user {user_id}")
        
        # Verify the updates
        print(f"\n🔍 VERIFICATION:")
        print("-" * 40)
        
        updated_users = await conn.fetch("""
            SELECT id, "jwtToken", "webhookApiKey", "webhookSecretKey" 
            FROM "User" 
            WHERE "jwtToken" IS NOT NULL 
            ORDER BY id
        """)
        
        for user in updated_users:
            print(f"User {user['id']}: ✅ JWT, ✅ API Key, ✅ Webhook Secret")
        
        await conn.close()
        print(f"\n✅ Test authentication data populated successfully!")
        
        print(f"\n📋 TESTING INSTRUCTIONS:")
        print("=" * 60)
        print("1. Start the server: python run_server.py")
        print("2. Go to http://localhost:8000/docs")
        print("3. Use any of the tokens/keys above to test authentication")
        print("4. The system will now validate against the database!")
        
    except Exception as e:
        logger.error(f"❌ Failed to populate test data: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(populate_test_auth_data())