"""
Service for managing conversations in MongoDB.
"""
from pymongo.errors import PyMongoError
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import os
import sys

# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger_config import get_logger
from utils.conversation_utils import generate_conversation_id_safe
from .connection import get_database

logger = get_logger(__name__)


class ConversationService:
    """Service for MongoDB conversation operations."""
    
    def __init__(self):
        """Initialize conversation service."""
        self.db = get_database()
        self.collection = self.db.conversations
    
    def generate_conversation_id(self) -> str:
        """Generate a conversation ID following the schema pattern: conv_[16 hex chars]."""
        return generate_conversation_id_safe("")
    
    def create_conversation(
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
            conversation_id = self.generate_conversation_id()
            now = timestamp or datetime.now(timezone.utc)
            
            conversation_doc = {
                "_id": conversation_id,
                "userId": user_id,
                "status": status,
                "createdAt": now,
                "updatedAt": now,
                "lastMessageAt": now,
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
            result = self.collection.insert_one(conversation_doc)
            
            if result.inserted_id:
                logger.info(f"✓ Created conversation: {conversation_id} (user: {user_id})")
                return conversation_id
            else:
                logger.error(f"Failed to create conversation: {conversation_id}")
                return None
                
        except PyMongoError as e:
            logger.error(f"MongoDB error creating conversation: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating conversation: {e}", exc_info=True)
            return None
    
    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get a conversation by ID."""
        try:
            conversation = self.collection.find_one({"_id": conversation_id})
            if conversation:
                logger.debug(f"Retrieved conversation: {conversation_id}")
            else:
                logger.debug(f"Conversation not found: {conversation_id}")
            return conversation
        except PyMongoError as e:
            logger.error(f"MongoDB error retrieving conversation: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error retrieving conversation: {e}", exc_info=True)
            return None
    
    def update_conversation(
        self,
        conversation_id: str,
        title: Optional[str] = None,
        status: Optional[str] = None,
        recent_messages: Optional[List[Dict[str, Any]]] = None,
        conversation_summary: Optional[Dict[str, Any]] = None,
        conversation_summaries: Optional[List[Dict[str, Any]]] = None,
        stats: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        client_info: Optional[Dict[str, Any]] = None,
        expires_at: Optional[datetime] = None,
        update_last_message: bool = False
    ) -> bool:
        """Update an existing conversation."""
        try:
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
            
            if conversation_summaries is not None:
                update_doc["conversationSummaries"] = conversation_summaries
            
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
            
            result = self.collection.update_one(
                {"_id": conversation_id},
                {"$set": update_doc}
            )
            
            if result.modified_count > 0:
                logger.info(f"✓ Updated conversation: {conversation_id}")
                return True
            else:
                logger.warning(f"No conversation updated: {conversation_id}")
                return False
                
        except PyMongoError as e:
            logger.error(f"MongoDB error updating conversation: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Unexpected error updating conversation: {e}", exc_info=True)
            return False
    
    def increment_message_count(
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
            now = datetime.now(timezone.utc)
            update_ops = {
                "$inc": {"stats.messageCount": 1},
                "$set": {"updatedAt": now}
            }
            
            if update_last_message:
                update_ops["$set"]["lastMessageAt"] = now
            
            result = self.collection.update_one(
                {"_id": conversation_id},
                update_ops
            )
            
            if result.modified_count > 0:
                logger.debug(f"✓ Incremented message count for conversation: {conversation_id}")
                return True
            else:
                logger.warning(f"No conversation found to increment message count: {conversation_id}")
                return False
                
        except PyMongoError as e:
            logger.error(f"MongoDB error incrementing message count: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Unexpected error incrementing message count: {e}", exc_info=True)
            return False
    
    def get_user_conversations(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """Get conversations for a user, ordered by last message time."""
        try:
            query = {"userId": user_id}
            if status:
                query["status"] = status
            
            conversations = list(
                self.collection.find(query)
                .sort("lastMessageAt", -1)
                .skip(skip)
                .limit(limit)
            )
            logger.debug(f"Retrieved {len(conversations)} conversations for user: {user_id}")
            return conversations
        except PyMongoError as e:
            logger.error(f"MongoDB error retrieving user conversations: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Unexpected error retrieving user conversations: {e}", exc_info=True)
            return []


# Global instance (singleton pattern)
_conversation_service: Optional[ConversationService] = None


def get_conversation_service() -> ConversationService:
    """Get or create Conversation service instance."""
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = ConversationService()
    return _conversation_service



