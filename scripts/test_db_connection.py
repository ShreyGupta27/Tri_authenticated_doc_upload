#!/usr/bin/env python3
"""
Simple database connection test.
"""
import asyncio
import asyncpg
from app.config import settings

async def test_connection():
    """Test basic database connection."""
    try:
        print(f"🔗 Connecting to: {settings.database_url}")
        conn = await asyncpg.connect(settings.database_url)
        print("✅ Connection successful!")
        
        # Test basic query
        version = await conn.fetchval('SELECT version()')
        print(f"📊 PostgreSQL version: {version}")
        
        # List databases
        databases = await conn.fetch("SELECT datname FROM pg_database WHERE datistemplate = false")
        print(f"📋 Available databases: {[db['datname'] for db in databases]}")
        
        await conn.close()
        print("✅ Connection closed successfully")
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print(f"🔍 Database URL: {settings.database_url}")

if __name__ == "__main__":
    asyncio.run(test_connection())