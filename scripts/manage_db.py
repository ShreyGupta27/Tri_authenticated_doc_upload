#!/usr/bin/env python3
"""
Database management script for the document upload service.
"""
import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import settings
from app.database import User, Base
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_test_users():
    """Create test users with JWT tokens and API keys for testing."""
    # Convert postgresql:// to postgresql+asyncpg://
    database_url = settings.database_url
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    engine = create_async_engine(database_url)
    
    try:
        async with engine.begin() as conn:
            # Create tables if they don't exist
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created/verified")
            
            # Check if test users already exist
            result = await conn.execute(text("SELECT COUNT(*) FROM users WHERE jwt_token IS NOT NULL"))
            count = result.scalar()
            
            if count > 0:
                logger.info(f"Found {count} existing users with JWT tokens")
                return
            
            # Insert test users
            test_users = [
                {
                    "jwt_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoidGVzdC11c2VyLTEyMyIsImV4cCI6MTc2ODEwOTcwM30.r5YUiz5ipSmcwyn6MQltze1zVkbQsEHarMJKEMPgKjA",
                    "webhook_api_key": "test-key-1",
                    "webhook_secret_key": "secret-123"
                },
                {
                    "jwt_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoidGVzdC11c2VyLTQ1NiIsImV4cCI6MTc2ODEwOTcwM30.example_token_2",
                    "webhook_api_key": "test-key-2",
                    "webhook_secret_key": "secret-456"
                },
                {
                    "jwt_token": None,
                    "webhook_api_key": "demo-key",
                    "webhook_secret_key": "demo-secret"
                }
            ]
            
            for user_data in test_users:
                await conn.execute(
                    text("""
                        INSERT INTO users ("jwtToken", "webhookApiKey", "webhookSecretKey") 
                        VALUES (:jwt_token, :webhook_api_key, :webhook_secret_key)
                    """),
                    user_data
                )
            
            logger.info(f"Created {len(test_users)} test users")
            
    except Exception as e:
        logger.error(f"Error creating test users: {e}")
        raise
    finally:
        await engine.dispose()


async def list_users():
    """List all users in the database."""
    database_url = settings.database_url
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    engine = create_async_engine(database_url)
    
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT id, "jwtToken", "webhookApiKey", "webhookSecretKey" 
                FROM users 
                ORDER BY id
            """))
            
            users = result.fetchall()
            
            print("\n📋 Users in Database:")
            print("=" * 80)
            print(f"{'ID':<5} {'JWT Token':<20} {'API Key':<15} {'Secret Key':<15}")
            print("-" * 80)
            
            for user in users:
                jwt_display = (user[1][:15] + "...") if user[1] else "None"
                api_display = user[2] if user[2] else "None"
                secret_display = user[3] if user[3] else "None"
                
                print(f"{user[0]:<5} {jwt_display:<20} {api_display:<15} {secret_display:<15}")
            
            print(f"\nTotal users: {len(users)}")
            
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise
    finally:
        await engine.dispose()


async def test_connection():
    """Test database connection."""
    database_url = settings.database_url
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    engine = create_async_engine(database_url)
    
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            logger.info(f"✅ Database connection successful!")
            logger.info(f"PostgreSQL version: {version}")
            
            # Test if users table exists
            result = await conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'users'
                )
            """))
            table_exists = result.scalar()
            
            if table_exists:
                result = await conn.execute(text("SELECT COUNT(*) FROM users"))
                user_count = result.scalar()
                logger.info(f"✅ Users table exists with {user_count} users")
            else:
                logger.warning("⚠️ Users table does not exist")
                
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        raise
    finally:
        await engine.dispose()


async def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python manage_db.py [test|create-users|list-users]")
        print("  test         - Test database connection")
        print("  create-users - Create test users")
        print("  list-users   - List all users")
        return
    
    command = sys.argv[1]
    
    if command == "test":
        await test_connection()
    elif command == "create-users":
        await create_test_users()
    elif command == "list-users":
        await list_users()
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    asyncio.run(main())