"""
MongoDB service for storing messages and conversations.
"""
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import secrets
import os
import sys

# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger_config import get_logger
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = get_logger(__name__)

from database.async_connection import get_async_database


class MongoDBService:
    """Service for MongoDB operations."""
    
    def __init__(self):
        self._db: Optional[AsyncIOMotorDatabase] = None
    
    async def _get_db(self) -> AsyncIOMotorDatabase:
        if self._db is None:
            self._db = await get_async_database()
        return self._db
    
    def generate_message_id(self) -> str:
        """Generate a message ID following the schema pattern: msg_[hex]"""
        return f"msg_{secrets.token_hex(8)}"
    
    async def save_user_message(
        self,
        conversation_id: str,
        user_id: str,
        content: str,
        message_type: str = "text",
        user_request: Optional[Dict[str, Any]] = None,
        input_tokens: Optional[int] = None,
        timestamp: Optional[datetime] = None
    ) -> Optional[str]:
        """
        Save a user message to MongoDB.
        
        Args:
            conversation_id: Conversation identifier (must match pattern: conv_[16 hex chars])
            user_id: User identifier (must match pattern: user_[alphanumeric_underscore])
            content: Message content
            message_type: Type of message (text, voice, image)
            user_request: Additional user request data
            input_tokens: Number of input tokens for this user message (optional)
            timestamp: Message timestamp (defaults to now)
            
        Returns:
            Message ID if successful, None otherwise
        """
        try:
            db = await self._get_db()
            message_id = self.generate_message_id()
            now = datetime.now(timezone.utc)
            
            message_doc = {
                "_id": message_id,
                "conversationId": conversation_id,
                "userId": user_id,
                "role": "user",
                "content": content,
                "messageType": message_type,
                "timestamp": timestamp or now,
                "createdAt": now,
            }
            
            # Add optional fields
            if user_request:
                message_doc["userRequest"] = user_request
            
            # Add token count if provided
            if input_tokens is not None:
                message_doc["tokens"] = {
                    "input": input_tokens,
                    "output": 0  # User messages don't have output tokens
                }
            
            # Insert into messages collection
            result = await db.messages.insert_one(message_doc)
            
            if result.inserted_id:
                logger.info(f"✓ Saved user message: {message_id} (conversation: {conversation_id}, input_tokens: {input_tokens})")
                return message_id
            else:
                logger.error(f"Failed to save user message: {message_id}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error saving user message: {e}", exc_info=True)
            return None
    
    async def save_assistant_message(
        self,
        conversation_id: str,
        user_id: str,
        content: str,
        intent: str,
        assistant_response: Optional[Dict[str, Any]] = None,
        agent_card: Optional[Dict[str, Any]] = None,
        suggested_agents: Optional[List[Dict[str, Any]]] = None,
        quick_actions: Optional[List[Dict[str, Any]]] = None,
        analytics_data: Optional[Dict[str, Any]] = None,
        processing: Optional[Dict[str, Any]] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        notice: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> Optional[str]:
        """
        Save an assistant message to MongoDB.

        Args:
            conversation_id: Conversation identifier
            user_id: User identifier
            content: Assistant response content
            intent: Detected intent
            assistant_response: Assistant response metadata
            agent_card: Agent card component data
            suggested_agents: Alternative agent suggestions
            quick_actions: Quick action buttons
            analytics_data: Analytics data (visualization, table_data, generated_sql, etc.)
            processing: Processing metadata (modelVersion, tokensUsed, latencyMs, requestId)
            input_tokens: Number of input tokens for this request (optional)
            output_tokens: Number of output tokens for this response (optional)
            timestamp: Message timestamp (defaults to now)

        Returns:
            Message ID if successful, None otherwise
        """
        try:
            db = await self._get_db()
            message_id = self.generate_message_id()
            now = datetime.now(timezone.utc)
            
            message_doc = {
                "_id": message_id,
                "conversationId": conversation_id,
                "userId": user_id,
                "role": "assistant",
                "content": content,
                "messageType": "text",
                "timestamp": timestamp or now,
                "createdAt": now,
            }
            if notice is not None:
                message_doc["notice"] = notice
            
            # Build assistantResponse object
            if assistant_response is None:
                assistant_response = {}
            if "intent" not in assistant_response:
                assistant_response["intent"] = intent
            
            message_doc["assistantResponse"] = assistant_response
            
            # Add optional fields
            if agent_card:
                message_doc["agentCard"] = agent_card
            
            if suggested_agents:
                message_doc["suggestedAgents"] = suggested_agents
            
            if quick_actions:
                message_doc["quickActions"] = quick_actions

            if analytics_data:
                message_doc["analyticsData"] = analytics_data

            # Add token counts to processing metadata or as separate field
            if processing is None:
                processing = {}
            
            # Update processing with token counts if provided
            if input_tokens is not None:
                processing["inputTokens"] = input_tokens
            if output_tokens is not None:
                processing["outputTokens"] = output_tokens
            if input_tokens is not None and output_tokens is not None:
                processing["tokensUsed"] = input_tokens + output_tokens
            
            # Also store tokens separately for easy querying
            if input_tokens is not None or output_tokens is not None:
                message_doc["tokens"] = {
                    "input": input_tokens or 0,
                    "output": output_tokens or 0
                }
            
            if processing:
                message_doc["processing"] = processing
            
            # Insert into messages collection
            result = await db.messages.insert_one(message_doc)
            
            if result.inserted_id:
                logger.info(f"✓ Saved assistant message: {message_id} (conversation: {conversation_id}, input_tokens: {input_tokens}, output_tokens: {output_tokens})")
                return message_id
            else:
                logger.error(f"Failed to save assistant message: {message_id}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error saving assistant message: {e}", exc_info=True)
            return None
    
    async def get_conversation_messages(
        self,
        conversation_id: str,
        limit: int = 50,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get messages for a conversation, ordered by timestamp.
        
        Args:
            conversation_id: Conversation identifier
            limit: Maximum number of messages to return
            skip: Number of messages to skip
            
        Returns:
            List of message documents
        """
        try:
            db = await self._get_db()
            cursor = (
                db.messages.find({"conversationId": conversation_id})
                .sort("timestamp", 1)
                .skip(skip)
                .limit(limit)
            )
            messages = await cursor.to_list(length=limit)
            logger.debug(f"Retrieved {len(messages)} messages for conversation: {conversation_id}")
            return messages
        except Exception as e:
            logger.error(f"Unexpected error retrieving messages: {e}", exc_info=True)
            return []


# Global instance (singleton pattern)
_mongodb_service: Optional[MongoDBService] = None


def get_mongodb_service() -> MongoDBService:
    """Get or create MongoDB service instance."""
    global _mongodb_service
    if _mongodb_service is None:
        _mongodb_service = MongoDBService()
    return _mongodb_service


