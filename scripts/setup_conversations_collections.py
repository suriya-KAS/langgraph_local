#!/usr/bin/env python3
"""
Script to create the conversations collection in MongoDB with validator and indexes.
"""

from pymongo import MongoClient
from pymongo.errors import CollectionInvalid, OperationFailure
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB connection string
MONGO_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = "msc-chatbot"
COLLECTION_NAME = "conversations"


def create_conversations_collection():
    """Create the conversations collection with validator and indexes."""
    try:
        # Connect to MongoDB with timeout settings
        print(f"Connecting to MongoDB...")
        client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=15000,  # 15 seconds to select server (increased from 5s)
            connectTimeoutMS=10000,  # 10 seconds to connect (increased from 5s)
            socketTimeoutMS=30000  # 30 seconds socket timeout (increased from 5s for operations)
        )
        db = client[DATABASE_NAME]
        
        # Test connection
        client.admin.command('ping')
        print(f"✓ Successfully connected to MongoDB database: {DATABASE_NAME}")
        
        # Define the validator schema (from NoSQL Schema/conversations.json)
        validator = {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["_id", "userId", "status", "createdAt", "updatedAt", "lastMessageAt"],
                "properties": {
                    "_id": {
                        "bsonType": "string",
                        "pattern": "^conv_[a-f0-9]{16}$",
                        "description": "Unique conversation ID with format conv_<16-char-hex>"
                    },
                    "userId": {
                        "bsonType": "string",
                        "pattern": "^user_[a-zA-Z0-9_]+$",
                        "description": "User identifier - required"
                    },
                    "status": {
                        "enum": ["active", "archived", "deleted"],
                        "description": "Conversation status - required"
                    },
                    "title": {
                        "bsonType": ["string", "null"],
                        "maxLength": 200,
                        "description": "Auto-generated or user-set conversation title"
                    },
                    "recentMessages": {
                        "bsonType": "array",
                        "maxItems": 10,
                        "items": {
                            "bsonType": "object",
                            "required": ["messageId", "role", "content", "timestamp"],
                            "properties": {
                                "messageId": {"bsonType": "string"},
                                "role": {"enum": ["user", "assistant", "system"]},
                                "content": {"bsonType": "string", "maxLength": 5000},
                                "timestamp": {"bsonType": "date"},
                                "intent": {"bsonType": ["string", "null"]},
                                "agentId": {"bsonType": ["string", "null"]}
                            }
                        }
                    },
                    "conversationSummary": {
                        "bsonType": ["object", "null"],
                        "description": "Summarized content of older messages for context window management",
                        "properties": {
                            "content": {
                                "bsonType": "string",
                                "maxLength": 5000,
                                "description": "Summarized content of older messages"
                            },
                            "messageCount": {
                                "bsonType": "int",
                                "minimum": 0,
                                "description": "Number of messages that were summarized"
                            },
                            "lastUpdated": {
                                "bsonType": "date",
                                "description": "When summary was last created or updated"
                            }
                        }
                    },
                    "stats": {
                        "bsonType": "object",
                        "required": ["messageCount", "totalTokensUsed", "totalCost"],
                        "properties": {
                            "messageCount": {
                                "bsonType": "int",
                                "minimum": 0,
                                "description": "Total number of messages in conversation"
                            },
                            "totalTokensUsed": {
                                "bsonType": "int",
                                "minimum": 0,
                                "description": "Total tokens consumed"
                            },
                            "totalCost": {
                                "bsonType": "double",
                                "minimum": 0,
                                "description": "Total cost"
                            }
                        }
                    },
                    "createdAt": {
                        "bsonType": "date",
                        "description": "Conversation creation timestamp - required"
                    },
                    "updatedAt": {
                        "bsonType": "date",
                        "description": "Last update timestamp - required"
                    },
                    "lastMessageAt": {
                        "bsonType": "date",
                        "description": "Timestamp of last message - required"
                    },
                    "expiresAt": {
                        "bsonType": ["date", "null"],
                        "description": "Expiration timestamp for TTL-based archival"
                    },
                    "metadata": {
                        "bsonType": "object",
                        "properties": {
                            "source": {
                                "enum": ["web", "mobile", "api"],
                                "description": "Source of conversation"
                            },
                            "satisfactionRating": {
                                "bsonType": ["int", "null"],
                                "minimum": 1,
                                "maximum": 5,
                                "description": "User satisfaction rating (1-5)"
                            },
                            "feedback": {
                                "bsonType": ["string", "null"],
                                "maxLength": 1000,
                                "description": "User feedback text"
                            }
                        }
                    },
                    "clientInfo": {
                        "bsonType": "object",
                        "properties": {
                            "device": {
                                "enum": ["mobile", "desktop", "tablet"],
                                "description": "Device type"
                            },
                            "appVersion": {
                                "bsonType": "string",
                                "description": "Application version"
                            },
                            "platform": {
                                "enum": ["ios", "android", "web"],
                                "description": "Platform type"
                            },
                            "timezone": {
                                "bsonType": "string",
                                "description": "User timezone (e.g., Asia/Kolkata)"
                            }
                        }
                    }
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
            # Index 1: Primary query pattern - Get user's conversations ordered by last activity
            {
                "keys": [("userId", 1), ("lastMessageAt", -1)],
                "name": "idx_userId_lastMessageAt",
                "background": True
            },
            # Index 2: Filter by user and status, ordered by last activity
            {
                "keys": [("userId", 1), ("status", 1), ("lastMessageAt", -1)],
                "name": "idx_userId_status_lastMessageAt",
                "background": True
            },
            # Index 3: Global conversation listing (admin/analytics)
            {
                "keys": [("status", 1), ("updatedAt", -1)],
                "name": "idx_status_updatedAt",
                "background": True
            },
            # Index 4: TTL index for auto-archival of expired conversations
            {
                "keys": [("expiresAt", 1)],
                "name": "idx_expiresAt_ttl",
                "expireAfterSeconds": 0,  # Expire immediately when expiresAt is reached
                "background": True,
                "partialFilterExpression": {"expiresAt": {"$ne": None}}  # Only index docs with expiresAt
            },
            # Index 5: Search by tags (optional, for categorization)
            {
                "keys": [("metadata.tags", 1), ("updatedAt", -1)],
                "name": "idx_tags_updatedAt",
                "background": True,
                "sparse": True  # Only index documents that have tags
            },
            # Index 6: Find conversations by creation date (analytics)
            {
                "keys": [("createdAt", -1)],
                "name": "idx_createdAt",
                "background": True
            }
        ]
        
        for index_spec in indexes:
            # Make a copy to avoid modifying the original
            spec_copy = index_spec.copy()
            keys = spec_copy.pop("keys")
            index_name = spec_copy.pop("name")
            
            try:
                # Check if index already exists
                existing_indexes = collection.list_indexes()
                index_exists = any(idx.get("name") == index_name for idx in existing_indexes)
                
                if index_exists:
                    print(f"  ⚠ Index '{index_name}' already exists, skipping...")
                else:
                    collection.create_index(keys, name=index_name, **spec_copy)
                    print(f"  ✓ Created index: {index_name}")
            except Exception as e:
                print(f"  ✗ Error creating index '{index_name}': {e}")
        
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
    success = create_conversations_collection()
    sys.exit(0 if success else 1)