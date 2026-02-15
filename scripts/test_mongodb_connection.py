#!/usr/bin/env python3
"""
Test script to verify MongoDB connection using MONGODB_URI from .env file.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, ConfigurationError

# Load environment variables from .env file
project_root = Path(__file__).parent.parent
env_file = project_root / ".env"

print("=" * 60)
print("MongoDB Connection Test")
print("=" * 60)

# Check if .env file exists
if not env_file.exists():
    print(f"\n⚠️  Warning: .env file not found at {env_file}")
    print("   Make sure you have a .env file in the project root.")
    print("   The script will still check for MONGODB_URI in environment variables.\n")
else:
    print(f"\n✓ Found .env file at: {env_file}")
    load_dotenv(env_file)
    print("✓ Environment variables loaded from .env file")

# Get MongoDB URI from environment
mongodb_uri = os.getenv("MONGODB_URI")

if not mongodb_uri:
    print("\n✗ Error: MONGODB_URI not found in environment variables")
    print("\nPlease ensure your .env file contains:")
    print("  MONGODB_URI=mongodb://localhost:27017/")
    print("  or")
    print("  MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/")
    sys.exit(1)

# Mask password in URI for display (security)
display_uri = mongodb_uri
if "@" in mongodb_uri:
    parts = mongodb_uri.split("@")
    if len(parts) == 2:
        auth_part = parts[0]
        if ":" in auth_part:
            user_pass = auth_part.split("://")[1] if "://" in auth_part else auth_part
            if ":" in user_pass:
                user, _ = user_pass.split(":", 1)
                display_uri = mongodb_uri.replace(f":{user_pass.split(':')[1]}", ":*****")

print(f"\n✓ MONGODB_URI found: {display_uri}")

# Test MongoDB connection
print("\n" + "-" * 60)
print("Testing MongoDB connection...")
print("-" * 60)

try:
    # Create MongoDB client
    print("\n1. Creating MongoDB client...")
    client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
    
    # Test connection with ping
    print("2. Testing connection with ping command...")
    client.admin.command('ping')
    print("   ✓ Ping successful!")
    
    # Get server info
    print("3. Retrieving server information...")
    server_info = client.server_info()
    print(f"   ✓ MongoDB version: {server_info.get('version', 'Unknown')}")
    
    # List databases
    print("4. Listing available databases...")
    db_names = client.list_database_names()
    print(f"   ✓ Found {len(db_names)} database(s):")
    for db_name in db_names[:10]:  # Show first 10
        print(f"      - {db_name}")
    if len(db_names) > 10:
        print(f"      ... and {len(db_names) - 10} more")
    
    # Test database access (msc-chatbot)
    print("\n5. Testing access to 'msc-chatbot' database...")
    db = client["msc-chatbot"]
    collections = db.list_collection_names()
    print(f"   ✓ Database 'msc-chatbot' accessible")
    print(f"   ✓ Found {len(collections)} collection(s):")
    for collection in collections[:10]:  # Show first 10
        count = db[collection].count_documents({})
        print(f"      - {collection} ({count} documents)")
    if len(collections) > 10:
        print(f"      ... and {len(collections) - 10} more")
    
    # Close connection
    client.close()
    
    print("\n" + "=" * 60)
    print("✓ MongoDB connection test PASSED!")
    print("=" * 60)
    print("\nConnection is working correctly. You can proceed with using MongoDB.")
    
except ServerSelectionTimeoutError as e:
    print(f"\n✗ Connection timeout: {e}")
    print("\nPossible issues:")
    print("  - MongoDB server is not running")
    print("  - Incorrect connection string")
    print("  - Network/firewall blocking the connection")
    print("  - Wrong host/port in MONGODB_URI")
    sys.exit(1)
    
except ConnectionFailure as e:
    print(f"\n✗ Connection failed: {e}")
    print("\nPossible issues:")
    print("  - MongoDB server is not running")
    print("  - Incorrect connection string")
    print("  - Authentication failed (wrong username/password)")
    sys.exit(1)
    
except ConfigurationError as e:
    print(f"\n✗ Configuration error: {e}")
    print("\nPossible issues:")
    print("  - Invalid MongoDB URI format")
    print("  - Missing required connection parameters")
    sys.exit(1)
    
except Exception as e:
    print(f"\n✗ Unexpected error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)








