#!/usr/bin/env python3
"""
Script to add new authentication credentials to specific users in the database.
"""
import asyncio
import asyncpg
from app.config import settings
import jwt
from datetime import datetime, timedelta, UTC
import secrets
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def add_jwt_token(user_id: int, expiry_hours: int = 24):
    """Add JWT token to a specific user."""
    try:
        conn = await asyncpg.connect(settings.database_url)
        
        # Generate JWT token
        jwt_payload = {
            "user_id": f"user-{user_id}",
            "exp": datetime.now(UTC) + timedelta(hours=expiry_hours)
        }
        jwt_token = jwt.encode(jwt_payload, settings.jwt_secret_key, algorithm="HS256")
        
        # Update user
        await conn.execute("""
            UPDATE "User" 
            SET "jwtToken" = $1
            WHERE id = $2
        """, jwt_token, user_id)
        
        print(f"✅ JWT token added to user {user_id}")
        print(f"   Token: {jwt_token}")
        print(f"   Expires: {expiry_hours} hours from now")
        
        await conn.close()
        return jwt_token
        
    except Exception as e:
        logger.error(f"❌ Failed to add JWT token: {e}")
        return None


async def add_api_key(user_id: int):
    """Add API key to a specific user."""
    try:
        conn = await asyncpg.connect(settings.database_url)
        
        # Generate API key
        api_key = f"jx_api_{secrets.token_hex(16)}"
        
        # Update user
        await conn.execute("""
            UPDATE "User" 
            SET "webhookApiKey" = $1
            WHERE id = $2
        """, api_key, user_id)
        
        print(f"✅ API key added to user {user_id}")
        print(f"   API Key: {api_key}")
        
        await conn.close()
        return api_key
        
    except Exception as e:
        logger.error(f"❌ Failed to add API key: {e}")
        return None


async def add_webhook_secret(user_id: int):
    """Add webhook secret to a specific user."""
    try:
        conn = await asyncpg.connect(settings.database_url)
        
        # Generate webhook secret
        webhook_secret = f"webhook_{secrets.token_hex(20)}"
        
        # Update user
        await conn.execute("""
            UPDATE "User" 
            SET "webhookSecretKey" = $1
            WHERE id = $2
        """, webhook_secret, user_id)
        
        print(f"✅ Webhook secret added to user {user_id}")
        print(f"   Webhook Secret: {webhook_secret}")
        
        await conn.close()
        return webhook_secret
        
    except Exception as e:
        logger.error(f"❌ Failed to add webhook secret: {e}")
        return None


async def add_all_credentials(user_id: int, expiry_hours: int = 24):
    """Add all three types of credentials to a user."""
    try:
        conn = await asyncpg.connect(settings.database_url)
        
        # Check if user exists
        user = await conn.fetchrow('SELECT id FROM "User" WHERE id = $1', user_id)
        if not user:
            print(f"❌ User {user_id} not found")
            await conn.close()
            return None
        
        # Generate all credentials
        jwt_payload = {
            "user_id": f"user-{user_id}",
            "exp": datetime.now(UTC) + timedelta(hours=expiry_hours)
        }
        jwt_token = jwt.encode(jwt_payload, settings.jwt_secret_key, algorithm="HS256")
        api_key = f"jx_api_{secrets.token_hex(16)}"
        webhook_secret = f"webhook_{secrets.token_hex(20)}"
        
        # Update user with all credentials
        await conn.execute("""
            UPDATE "User" 
            SET "jwtToken" = $1, "webhookApiKey" = $2, "webhookSecretKey" = $3
            WHERE id = $4
        """, jwt_token, api_key, webhook_secret, user_id)
        
        print(f"✅ All credentials added to user {user_id}")
        print(f"   JWT Token: {jwt_token}")
        print(f"   API Key: {api_key}")
        print(f"   Webhook Secret: {webhook_secret}")
        print(f"   JWT Expires: {expiry_hours} hours from now")
        
        await conn.close()
        return {
            "jwt_token": jwt_token,
            "api_key": api_key,
            "webhook_secret": webhook_secret
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to add credentials: {e}")
        return None


async def list_users():
    """List all users and their current credentials."""
    try:
        conn = await asyncpg.connect(settings.database_url)
        
        users = await conn.fetch("""
            SELECT id, email, firstName, lastName, 
                   "jwtToken", "webhookApiKey", "webhookSecretKey"
            FROM "User" 
            ORDER BY id
        """)
        
        print("\n👥 USERS IN DATABASE:")
        print("=" * 80)
        
        for user in users:
            jwt_status = "✅" if user['jwtToken'] else "❌"
            api_status = "✅" if user['webhookApiKey'] else "❌"
            webhook_status = "✅" if user['webhookSecretKey'] else "❌"
            
            name = f"{user['firstName'] or ''} {user['lastName'] or ''}".strip()
            if not name:
                name = "No name"
            
            print(f"ID: {user['id']:<3} | {name:<20} | {user['email']:<25}")
            print(f"         JWT: {jwt_status} | API Key: {api_status} | Webhook: {webhook_status}")
            print("-" * 80)
        
        await conn.close()
        
    except Exception as e:
        logger.error(f"❌ Failed to list users: {e}")


async def remove_credentials(user_id: int, credential_type: str = "all"):
    """Remove credentials from a user."""
    try:
        conn = await asyncpg.connect(settings.database_url)
        
        if credential_type == "all":
            await conn.execute("""
                UPDATE "User" 
                SET "jwtToken" = NULL, "webhookApiKey" = NULL, "webhookSecretKey" = NULL
                WHERE id = $1
            """, user_id)
            print(f"✅ All credentials removed from user {user_id}")
            
        elif credential_type == "jwt":
            await conn.execute("""
                UPDATE "User" 
                SET "jwtToken" = NULL
                WHERE id = $1
            """, user_id)
            print(f"✅ JWT token removed from user {user_id}")
            
        elif credential_type == "api":
            await conn.execute("""
                UPDATE "User" 
                SET "webhookApiKey" = NULL
                WHERE id = $1
            """, user_id)
            print(f"✅ API key removed from user {user_id}")
            
        elif credential_type == "webhook":
            await conn.execute("""
                UPDATE "User" 
                SET "webhookSecretKey" = NULL
                WHERE id = $1
            """, user_id)
            print(f"✅ Webhook secret removed from user {user_id}")
        
        await conn.close()
        
    except Exception as e:
        logger.error(f"❌ Failed to remove credentials: {e}")


def print_usage():
    """Print usage instructions."""
    print("""
🔑 CREDENTIAL MANAGEMENT COMMANDS
================================

List all users:
    python add_credentials.py list

Add JWT token to user:
    python add_credentials.py jwt <user_id> [expiry_hours]
    Example: python add_credentials.py jwt 5 48

Add API key to user:
    python add_credentials.py api <user_id>
    Example: python add_credentials.py api 5

Add webhook secret to user:
    python add_credentials.py webhook <user_id>
    Example: python add_credentials.py webhook 5

Add all credentials to user:
    python add_credentials.py all <user_id> [expiry_hours]
    Example: python add_credentials.py all 5 24

Remove credentials from user:
    python add_credentials.py remove <user_id> [type]
    Types: all, jwt, api, webhook
    Example: python add_credentials.py remove 5 jwt
    """)


async def main():
    """Main function to handle command line arguments."""
    if len(sys.argv) < 2:
        print_usage()
        return
    
    command = sys.argv[1].lower()
    
    if command == "list":
        await list_users()
        
    elif command == "jwt":
        if len(sys.argv) < 3:
            print("❌ User ID required")
            return
        user_id = int(sys.argv[2])
        expiry_hours = int(sys.argv[3]) if len(sys.argv) > 3 else 24
        await add_jwt_token(user_id, expiry_hours)
        
    elif command == "api":
        if len(sys.argv) < 3:
            print("❌ User ID required")
            return
        user_id = int(sys.argv[2])
        await add_api_key(user_id)
        
    elif command == "webhook":
        if len(sys.argv) < 3:
            print("❌ User ID required")
            return
        user_id = int(sys.argv[2])
        await add_webhook_secret(user_id)
        
    elif command == "all":
        if len(sys.argv) < 3:
            print("❌ User ID required")
            return
        user_id = int(sys.argv[2])
        expiry_hours = int(sys.argv[3]) if len(sys.argv) > 3 else 24
        await add_all_credentials(user_id, expiry_hours)
        
    elif command == "remove":
        if len(sys.argv) < 3:
            print("❌ User ID required")
            return
        user_id = int(sys.argv[2])
        credential_type = sys.argv[3] if len(sys.argv) > 3 else "all"
        await remove_credentials(user_id, credential_type)
        
    else:
        print(f"❌ Unknown command: {command}")
        print_usage()


if __name__ == "__main__":
    asyncio.run(main())