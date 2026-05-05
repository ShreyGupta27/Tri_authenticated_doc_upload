#!/usr/bin/env python3
"""
Simple database setup script.
"""
import asyncio
import asyncpg
from app.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def setup_database():
    """Set up database with test data."""
    try:
        # Connect to database
        conn = await asyncpg.connect(settings.database_url)
        logger.info("✅ Connected to database")
        
        # Create users table if it doesn't exist
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                "jwtToken" TEXT,
                "webhookApiKey" TEXT,
                "webhookSecretKey" TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        logger.info("✅ Users table created/verified")
        
        # Check if we have test data
        count = await conn.fetchval('SELECT COUNT(*) FROM users WHERE "jwtToken" IS NOT NULL')
        
        if count == 0:
            # Insert test users
            test_users = [
                {
                    'jwt_token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoidGVzdC11c2VyLTEyMyIsImV4cCI6MTc2ODEwOTcwM30.r5YUiz5ipSmcwyn6MQltze1zVkbQsEHarMJKEMPgKjA',
                    'api_key': 'test-key-1',
                    'secret_key': 'secret-123'
                },
                {
                    'jwt_token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoidGVzdC11c2VyLTQ1NiIsImV4cCI6MTc2ODEwOTcwM30.example_token_2',
                    'api_key': 'test-key-2', 
                    'secret_key': 'secret-456'
                },
                {
                    'jwt_token': None,
                    'api_key': 'demo-key',
                    'secret_key': 'demo-secret'
                }
            ]
            
            for user in test_users:
                await conn.execute('''
                    INSERT INTO users ("jwtToken", "webhookApiKey", "webhookSecretKey") 
                    VALUES ($1, $2, $3)
                ''', user['jwt_token'], user['api_key'], user['secret_key'])
            
            logger.info(f"✅ Created {len(test_users)} test users")
        else:
            logger.info(f"✅ Found {count} existing users")
        
        # List all users
        users = await conn.fetch('SELECT id, "jwtToken", "webhookApiKey", "webhookSecretKey" FROM users ORDER BY id')
        
        print("\n📋 Users in Database:")
        print("=" * 100)
        print(f"{'ID':<5} {'JWT Token':<30} {'API Key':<15} {'Secret Key':<15}")
        print("-" * 100)
        
        for user in users:
            jwt_display = (user['jwtToken'][:25] + "...") if user['jwtToken'] else "None"
            api_display = user['webhookApiKey'] if user['webhookApiKey'] else "None"
            secret_display = user['webhookSecretKey'] if user['webhookSecretKey'] else "None"
            
            print(f"{user['id']:<5} {jwt_display:<30} {api_display:<15} {secret_display:<15}")
        
        print(f"\n✅ Database setup complete! Total users: {len(users)}")
        print("\n🔑 Test Credentials:")
        print("JWT Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoidGVzdC11c2VyLTEyMyIsImV4cCI6MTc2ODEwOTcwM30.r5YUiz5ipSmcwyn6MQltze1zVkbQsEHarMJKEMPgKjA")
        print("API Key: test-key-1")
        
        await conn.close()
        
    except Exception as e:
        logger.error(f"❌ Database setup failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(setup_database())