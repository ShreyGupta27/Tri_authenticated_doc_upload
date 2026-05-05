#!/usr/bin/env python3
"""
Database exploration script to see tables, columns, and data.
"""
import asyncio
import asyncpg
from app.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def explore_database():
    """Explore the database structure and data."""
    try:
        conn = await asyncpg.connect(settings.database_url)
        logger.info("✅ Connected to database")
        
        print("\n" + "="*80)
        print("🗄️  DATABASE EXPLORATION")
        print("="*80)
        
        # 1. List all tables
        print("\n📋 ALL TABLES:")
        print("-" * 50)
        tables = await conn.fetch("""
            SELECT table_name, table_type 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        
        if tables:
            for table in tables:
                print(f"  📄 {table['table_name']} ({table['table_type']})")
        else:
            print("  ❌ No tables found in public schema")
        
        # 2. Check if User table exists and show its structure (note: capitalized)
        user_table = await conn.fetchrow("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'User'
        """)
        
        if user_table:
            print(f"\n🔍 USER TABLE STRUCTURE:")
            print("-" * 50)
            
            # Get column information
            columns = await conn.fetch("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_schema = 'public' AND table_name = 'User'
                ORDER BY ordinal_position
            """)
            
            for col in columns:
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
                print(f"  📊 {col['column_name']:<20} {col['data_type']:<15} {nullable}{default}")
            
            # Check for authentication columns
            column_names = [col['column_name'] for col in columns]
            auth_columns = ['jwtToken', 'webhookApiKey', 'webhookSecretKey']
            
            print(f"\n🔑 AUTHENTICATION COLUMNS CHECK:")
            print("-" * 50)
            for auth_col in auth_columns:
                if auth_col in column_names:
                    print(f"  ✅ {auth_col} - Found")
                else:
                    print(f"  ❌ {auth_col} - Missing")
            
            # Show data in User table
            print(f"\n📊 USER TABLE DATA:")
            print("-" * 50)
            
            users = await conn.fetch('SELECT * FROM "User" ORDER BY id LIMIT 10')
            
            if users:
                # Get column names
                col_names = list(users[0].keys())
                
                # Print header
                header = " | ".join(f"{col:<15}" for col in col_names)
                print(f"  {header}")
                print("  " + "-" * len(header))
                
                # Print data
                for user in users:
                    row_data = []
                    for col in col_names:
                        value = user[col]
                        if value is None:
                            display_value = "NULL"
                        elif isinstance(value, str) and len(value) > 12:
                            display_value = value[:9] + "..."
                        else:
                            display_value = str(value)
                        row_data.append(f"{display_value:<15}")
                    
                    print(f"  {' | '.join(row_data)}")
                
                print(f"\n  📈 Total users: {len(users)}")
                
                # Show full tokens for testing (if auth columns exist)
                if any(col in column_names for col in auth_columns):
                    print(f"\n🔑 FULL CREDENTIALS FOR TESTING:")
                    print("-" * 50)
                    
                    for i, user in enumerate(users[:3], 1):  # Show first 3 users
                        print(f"\n  User {user.get('id', 'N/A')}:")
                        if 'jwtToken' in column_names and user.get('jwtToken'):
                            print(f"    JWT Token: {user['jwtToken']}")
                        if 'webhookApiKey' in column_names and user.get('webhookApiKey'):
                            print(f"    API Key: {user['webhookApiKey']}")
                        if 'webhookSecretKey' in column_names and user.get('webhookSecretKey'):
                            print(f"    Secret Key: {user['webhookSecretKey']}")
                
            else:
                print("  ❌ No users found in table")
        
        else:
            print(f"\n❌ User table does not exist")
            
            # Check what tables do exist
            print(f"\n🔍 AVAILABLE TABLES:")
            all_tables = await conn.fetch("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            
            for table in all_tables:
                print(f"  📄 {table['table_name']}")
        
        # 3. Database info
        print(f"\n🏗️  DATABASE INFO:")
        print("-" * 50)
        
        db_info = await conn.fetchrow("SELECT current_database(), current_user, version()")
        print(f"  Database: {db_info['current_database']}")
        print(f"  User: {db_info['current_user']}")
        print(f"  Version: {db_info['version']}")
        
        await conn.close()
        print(f"\n✅ Database exploration complete!")
        
    except Exception as e:
        logger.error(f"❌ Database exploration failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(explore_database())