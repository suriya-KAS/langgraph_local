"""
MongoDB service for storing conversations.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import os
import sys

# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger_config import get_logger
from utils.conversation_utils import generate_conversation_id_safe
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = get_logger(__name__)

from motor.motor_asyncio import AsyncIOMotorDatabase
from database.async_connection import get_async_database


class ConversationsService:
    """Service for MongoDB conversations operations."""
    
    def __init__(self):
        self._db: Optional[AsyncIOMotorDatabase] = None
    
    async def _get_db(self) -> AsyncIOMotorDatabase:
        if self._db is None:
            self._db = await get_async_database()
        return self._db
    
    def generate_conversation_id(self) -> str:
        """
        Generate a conversation ID following the schema pattern: conv_[16 hex chars]
        
        Uses centralized function from conversation_utils for consistency across the codebase.
        """
        # Use centralized function for consistency (user_id parameter kept for API compatibility)
        return generate_conversation_id_safe("")
    
    async def create_conversation(
        self,
        user_id: str,
        title: Optional[str] = None,
        status: str = "active",
        metadata: Optional[Dict[str, Any]] = None,
        client_info: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ) -> Optional[str]:
        """
        Create a new conversation.
        
        Args:
            user_id: User identifier (must match pattern: user_[alphanumeric_underscore])
            title: Conversation title (optional)
            status: Conversation status (active, archived, deleted)
            metadata: Additional metadata
            client_info: Client information (device, platform, etc.)
            timestamp: Creation timestamp (defaults to now)
            
        Returns:
            Conversation ID if successful, None otherwise
        """
        try:
            db = await self._get_db()
            conversation_id = self.generate_conversation_id()
            now = datetime.now(timezone.utc)
            
            conversation_doc = {
                "_id": conversation_id,
                "userId": user_id,
                "status": status,
                "createdAt": timestamp or now,
                "updatedAt": timestamp or now,
                "lastMessageAt": timestamp or now,
                "stats": {
                    "messageCount": 0,
                    "totalTokensUsed": 0,
                    "totalCost": 0.0
                }
            }
            
            # Add optional fields
            if title:
                conversation_doc["title"] = title
            
            if metadata:
                conversation_doc["metadata"] = metadata
            
            if client_info:
                conversation_doc["clientInfo"] = client_info
            
            # Insert into conversations collection
            result = await db.conversations.insert_one(conversation_doc)
            
            if result.inserted_id:
                logger.info(f"✓ Created conversation: {conversation_id} (user: {user_id})")
                return conversation_id
            else:
                logger.error(f"Failed to create conversation: {conversation_id}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error creating conversation: {e}", exc_info=True)
            return None
    
    async def update_conversation(
        self,
        conversation_id: str,
        title: Optional[str] = None,
        status: Optional[str] = None,
        recent_messages: Optional[List[Dict[str, Any]]] = None,
        conversation_summary: Optional[Dict[str, Any]] = None,
        stats: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        client_info: Optional[Dict[str, Any]] = None,
        expires_at: Optional[datetime] = None,
        update_last_message: bool = False
    ) -> bool:
        """
        Update an existing conversation.
        
        Args:
            conversation_id: Conversation identifier
            title: Conversation title
            status: Conversation status
            recent_messages: Recent messages array (max 10)
            conversation_summary: Conversation summary object
            stats: Stats object (messageCount, totalTokensUsed, totalCost)
            metadata: Metadata object
            client_info: Client info object
            expires_at: Expiration timestamp
            update_last_message: Whether to update lastMessageAt timestamp
            
        Returns:
            True if successful, False otherwise
        """
        try:
            db = await self._get_db()
            update_doc = {}
            now = datetime.now(timezone.utc)
            
            if title is not None:
                update_doc["title"] = title
            
            if status is not None:
                update_doc["status"] = status
            
            if recent_messages is not None:
                update_doc["recentMessages"] = recent_messages
            
            if conversation_summary is not None:
                update_doc["conversationSummary"] = conversation_summary
            
            if stats is not None:
                update_doc["stats"] = stats
            
            if metadata is not None:
                update_doc["metadata"] = metadata
            
            if client_info is not None:
                update_doc["clientInfo"] = client_info
            
            if expires_at is not None:
                update_doc["expiresAt"] = expires_at
            
            if update_last_message:
                update_doc["lastMessageAt"] = now
            
            # Always update updatedAt
            update_doc["updatedAt"] = now
            
            if not update_doc:
                logger.warning(f"No fields to update for conversation: {conversation_id}")
                return False
            
            result = await db.conversations.update_one(
                {"_id": conversation_id},
                {"$set": update_doc}
            )
            
            if result.modified_count > 0:
                logger.info(f"✓ Updated conversation: {conversation_id}")
                return True
            else:
                logger.warning(f"No conversation updated: {conversation_id}")
                return False
                
        except Exception as e:
            logger.error(f"Unexpected error updating conversation: {e}", exc_info=True)
            return False
    
    async def increment_message_count(
        self,
        conversation_id: str,
        update_last_message: bool = True
    ) -> bool:
        """
        Atomically increment the message count in conversation stats.
        
        Args:
            conversation_id: Conversation identifier
            update_last_message: Whether to update lastMessageAt timestamp
            
        Returns:
            True if successful, False otherwise
        """
        try:
            db = await self._get_db()
            now = datetime.now(timezone.utc)
            update_ops = {
                "$inc": {"stats.messageCount": 1},
                "$set": {"updatedAt": now}
            }
            
            if update_last_message:
                update_ops["$set"]["lastMessageAt"] = now
            
            result = await db.conversations.update_one(
                {"_id": conversation_id},
                update_ops
            )
            
            if result.modified_count > 0:
                logger.debug(f"✓ Incremented message count for conversation: {conversation_id}")
                return True
            else:
                logger.warning(f"No conversation found to increment message count: {conversation_id}")
                return False
                
        except Exception as e:
            logger.error(f"Unexpected error incrementing message count: {e}", exc_info=True)
            return False
    
    async def get_conversation(
        self,
        conversation_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a conversation by ID.
        
        Args:
            conversation_id: Conversation identifier
            
        Returns:
            Conversation document if found, None otherwise
        """
        try:
            db = await self._get_db()
            conversation = await db.conversations.find_one({"_id": conversation_id})
            if conversation:
                logger.debug(f"Retrieved conversation: {conversation_id}")
            else:
                logger.debug(f"Conversation not found: {conversation_id}")
            return conversation
        except Exception as e:
            logger.error(f"Unexpected error retrieving conversation: {e}", exc_info=True)
            return None
    
    async def get_user_conversations(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get conversations for a user, ordered by last message time.
        
        Args:
            user_id: User identifier
            status: Filter by status (optional)
            limit: Maximum number of conversations to return
            skip: Number of conversations to skip
            
        Returns:
            List of conversation documents
        """
        try:
            db = await self._get_db()
            query = {"userId": user_id}
            if status:
                query["status"] = status
            
            cursor = (
                db.conversations.find(query)
                .sort("lastMessageAt", -1)
                .skip(skip)
                .limit(limit)
            )
            conversations = await cursor.to_list(length=limit)
            logger.debug(f"Retrieved {len(conversations)} conversations for user: {user_id}")
            return conversations
        except Exception as e:
            logger.error(f"Unexpected error retrieving user conversations: {e}", exc_info=True)
            return []
    
    async def delete_conversation(
        self,
        conversation_id: str,
        hard_delete: bool = False
    ) -> bool:
        """
        Delete or archive a conversation.
        
        Args:
            conversation_id: Conversation identifier
            hard_delete: If True, permanently delete. If False, mark as deleted.
            
        Returns:
            True if successful, False otherwise
        """
        try:
            db = await self._get_db()
            if hard_delete:
                result = await db.conversations.delete_one({"_id": conversation_id})
                if result.deleted_count > 0:
                    logger.info(f"✓ Hard deleted conversation: {conversation_id}")
                    return True
            else:
                result = await db.conversations.update_one(
                    {"_id": conversation_id},
                    {
                        "$set": {
                            "status": "deleted",
                            "updatedAt": datetime.now(timezone.utc)
                        }
                    }
                )
                if result.modified_count > 0:
                    logger.info(f"✓ Archived conversation: {conversation_id}")
                    return True
            
            logger.warning(f"No conversation found to delete: {conversation_id}")
            return False
                
        except Exception as e:
            logger.error(f"Unexpected error deleting conversation: {e}", exc_info=True)
            return False


# Global instance (singleton pattern)
_conversations_service: Optional[ConversationsService] = None


def get_conversations_service() -> ConversationsService:
    """Get or create Conversations service instance."""
    global _conversations_service
    if _conversations_service is None:
        _conversations_service = ConversationsService()
    return _conversations_service


if __name__ == "__main__":
    """Test the conversations service and create collection."""
    print("=" * 60)
    print("Testing Conversations Service")
    print("=" * 60)
    
    try:
        # Initialize service (this will connect to MongoDB)
        service = get_conversations_service()
        print("✓ Connected to MongoDB")
        
        # Test creating a conversation (this will create the collection)
        test_user_id = "user_test_123"
        conv_id = service.create_conversation(
            user_id=test_user_id,
            title="Test Conversation",
            status="active"
        )
        
        if conv_id:
            print(f"✓ Created test conversation: {conv_id}")
            print(f"✓ Collection 'conversations' is now created")
            
            # Clean up test conversation
            service.delete_conversation(conv_id, hard_delete=True)
            print(f"✓ Cleaned up test conversation")
        else:
            print("✗ Failed to create test conversation")
        
        # Close connection
        service.close()
        print("\n✓ Test completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 60)

