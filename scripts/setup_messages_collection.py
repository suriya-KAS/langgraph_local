#!/usr/bin/env python3
"""
Script to create the messages collection in MongoDB with validator and indexes.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import CollectionInvalid, OperationFailure

load_dotenv()


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


# MongoDB connection string (required)
MONGO_URI = _get_required_env("MONGODB_URI")
DATABASE_NAME = os.getenv("MONGODB_DATABASE", "msc-chatbot")
COLLECTION_NAME = "messages"


def create_messages_collection():
    """Create the messages collection with validator and indexes."""
    try:
        # Connect to MongoDB
        print(f"Connecting to MongoDB...")
        client = MongoClient(MONGO_URI)
        db = client[DATABASE_NAME]
        
        # Test connection
        client.admin.command('ping')
        print(f"✓ Successfully connected to MongoDB database: {DATABASE_NAME}")
        
        # Define the validator schema
        validator = {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["_id", "conversationId", "userId", "role", "content", "timestamp", "createdAt"],
                "properties": {
                    "_id": {
                        "bsonType": "string",
                        "pattern": "^msg_[a-f0-9]+$",
                        "description": "Unique message ID"
                    },
                    "conversationId": {
                        "bsonType": "string",
                        "pattern": "^conv_[a-f0-9]{16}$",
                        "description": "Reference to conversation"
                    },
                    "userId": {
                        "bsonType": "string",
                        "pattern": "^user_[a-zA-Z0-9_]+$",
                        "description": "User identifier"
                    },
                    "role": {
                        "enum": ["user", "assistant", "system"],
                        "description": "Message sender role"
                    },
                    "content": {
                        "bsonType": "string",
                        "description": "Message content"
                    },
                    "messageType": {
                        "enum": ["text", "voice", "image"],
                        "description": "Type of message"
                    },
                    "userRequest": {
                        "bsonType": ["object", "null"],
                        "description": "Original user request data"
                    },
                    "assistantResponse": {
                        "bsonType": ["object", "null"],
                        "description": "Assistant response metadata"
                    },
                    "agentCard": {
                        "bsonType": ["object", "null"],
                        "description": "Agent card component"
                    },
                    "suggestedAgents": {
                        "bsonType": ["array", "null"],
                        "description": "Alternative agent suggestions"
                    },
                    "quickActions": {
                        "bsonType": ["array", "null"],
                        "description": "Quick action buttons"
                    },
                    "analyticsData": {
                        "bsonType": ["object", "null"],
                        "description": "Analytics data (visualization, table_data, generated_sql, row_count, etc.)"
                    },
                    "media": {
                        "bsonType": ["array", "null"],
                        "description": "Media attachments"
                    },
                    "processing": {
                        "bsonType": ["object", "null"],
                        "properties": {
                            "modelVersion": {"bsonType": "string"},
                            "tokensUsed": {"bsonType": ["int", "null"]},
                            "latencyMs": {"bsonType": ["double", "null"]},
                            "requestId": {"bsonType": ["string", "null"]}
                        }
                    },
                    "error": {
                        "bsonType": ["object", "null"],
                        "properties": {
                            "code": {"bsonType": ["string", "null"]},
                            "message": {"bsonType": ["string", "null"]},
                            "timestamp": {"bsonType": ["date", "null"]}
                        }
                    },
                    "timestamp": {"bsonType": "date"},
                    "createdAt": {"bsonType": "date"}
                }
            }
        }
        
        # Collection options
        collection_options = {
            "validator": validator,
            "validationLevel": "moderate",
            "validationAction": "warn"
        }
        
        # Check if collection already exists
        if COLLECTION_NAME in db.list_collection_names():
            print(f"⚠ Collection '{COLLECTION_NAME}' already exists.")
            response = input("Do you want to drop and recreate it? (yes/no): ").strip().lower()
            if response == "yes":
                print(f"Dropping existing collection '{COLLECTION_NAME}'...")
                db.drop_collection(COLLECTION_NAME)
                print(f"✓ Collection dropped")
            else:
                print("Keeping existing collection. Updating validator only...")
                try:
                    db.command({
                        "collMod": COLLECTION_NAME,
                        "validator": validator,
                        "validationLevel": "moderate",
                        "validationAction": "warn"
                    })
                    print(f"✓ Validator updated for collection '{COLLECTION_NAME}'")
                except OperationFailure as e:
                    print(f"✗ Error updating validator: {e}")
                    return False
        
        # Create collection if it doesn't exist
        if COLLECTION_NAME not in db.list_collection_names():
            print(f"Creating collection '{COLLECTION_NAME}' with validator...")
            db.create_collection(COLLECTION_NAME, **collection_options)
            print(f"✓ Collection '{COLLECTION_NAME}' created successfully")
        
        # Create indexes
        collection = db[COLLECTION_NAME]
        print("\nCreating indexes...")
        
        indexes = [
            # Compound index for conversationId and timestamp
            {
                "keys": [("conversationId", 1), ("timestamp", 1)],
                "name": "conversationId_timestamp_idx"
            },
            # Compound index for userId and timestamp (descending)
            {
                "keys": [("userId", 1), ("timestamp", -1)],
                "name": "userId_timestamp_idx"
            },
            # Compound index for assistantResponse.intent and timestamp
            {
                "keys": [("assistantResponse.intent", 1), ("timestamp", -1)],
                "name": "assistantResponse_intent_timestamp_idx"
            },
            # Compound index for agentCard.agentId and timestamp
            {
                "keys": [("agentCard.agentId", 1), ("timestamp", -1)],
                "name": "agentCard_agentId_timestamp_idx"
            },
            # Sparse index for error.code
            {
                "keys": [("error.code", 1)],
                "name": "error_code_idx",
                "sparse": True
            },
            # TTL index on timestamp (90 days = 7776000 seconds)
            {
                "keys": [("timestamp", 1)],
                "name": "timestamp_ttl_idx",
                "expireAfterSeconds": 7776000
            }
        ]
        
        for index_spec in indexes:
            try:
                keys = index_spec.pop("keys")
                index_name = index_spec.pop("name")
                
                # Check if index already exists
                existing_indexes = collection.list_indexes()
                index_exists = any(idx.get("name") == index_name for idx in existing_indexes)
                
                if index_exists:
                    print(f"  ⚠ Index '{index_name}' already exists, skipping...")
                else:
                    collection.create_index(keys, name=index_name, **index_spec)
                    print(f"  ✓ Created index: {index_name}")
            except Exception as e:
                print(f"  ✗ Error creating index '{index_spec.get('name', 'unknown')}': {e}")
        
        # List all indexes
        print("\n" + "="*50)
        print("Collection indexes:")
        print("="*50)
        for index in collection.list_indexes():
            print(f"  - {index['name']}: {index.get('key', {})}")
        
        print("\n" + "="*50)
        print(f"✓ Successfully set up collection '{COLLECTION_NAME}'")
        print("="*50)
        
        client.close()
        return True
        
    except CollectionInvalid as e:
        print(f"✗ Collection creation error: {e}")
        return False
    except OperationFailure as e:
        print(f"✗ MongoDB operation error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = create_messages_collection()
    sys.exit(0 if success else 1)

