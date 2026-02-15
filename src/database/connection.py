"""
MongoDB connection management.
"""
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from typing import Optional
import os
import sys

# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger_config import get_logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = get_logger(__name__)

# MongoDB configuration
MONGO_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("MONGODB_DATABASE", "msc-chatbot")


class DatabaseConnection:
    """Manages MongoDB connection and provides database access."""
    
    def __init__(self):
        """Initialize MongoDB connection."""
        if not MONGO_URI:
            raise ValueError("MONGODB_URI environment variable is not set")
        
        try:
            self.client = MongoClient(
                MONGO_URI,
                serverSelectionTimeoutMS=15000,  # 15 seconds to select server (increased from 5s)
                connectTimeoutMS=10000,  # 10 seconds to connect (increased from 5s)
                socketTimeoutMS=30000  # 30 seconds socket timeout (increased from 5s for operations)
            )
            self.db = self.client[DATABASE_NAME]
            # Test connection
            self.client.admin.command('ping')
            logger.info(f"✓ Connected to MongoDB database: {DATABASE_NAME}")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}", exc_info=True)
            raise
    
    def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.debug("MongoDB connection closed")
    
    def get_database(self):
        """Get the database instance."""
        return self.db


# Global instance (singleton pattern)
_database_connection: Optional[DatabaseConnection] = None


def get_database():
    """Get or create database connection instance."""
    global _database_connection
    if _database_connection is None:
        _database_connection = DatabaseConnection()
    return _database_connection.get_database()


def close_database():
    """Close database connection."""
    global _database_connection
    if _database_connection:
        _database_connection.close()
        _database_connection = None








