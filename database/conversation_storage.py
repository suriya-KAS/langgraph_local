"""
Dynamic conversation storage service for chatbot.

This service handles:
1. Creating new conversations when a fresh chat starts
2. Storing messages (both user and assistant) with conversationId
3. Managing conversation lifecycle
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
from .schema.conversations import get_conversations_service, ConversationsService
from .schema.messages import get_mongodb_service, MongoDBService

logger = get_logger(__name__)


class ConversationStorage:
    """
    Service for managing conversations and messages dynamically.
    
    This service ensures that:
    - A new conversationId is created when a fresh chat starts
    - All messages in a conversation share the same conversationId
    - Each message (user or assistant) is stored as a separate document
    """
    
    def __init__(self):
        """Initialize conversation storage service."""
        self.conversations_service = get_conversations_service()
        self.messages_service = get_mongodb_service()
        logger.debug("ConversationStorage initialized")
    
    async def get_or_create_conversation(
        self,
        user_id: str,
        conversation_id: Optional[str] = None,
        client_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Get existing conversation or create a new one.
        
        If conversation_id is provided and exists, return it.
        If conversation_id is None, empty, or doesn't exist, create a new conversation.
        
        Args:
            user_id: User identifier
            conversation_id: Existing conversation ID (optional)
            client_info: Client information (device, platform, etc.)
            
        Returns:
            Conversation ID (existing or newly created)
        """
        try:
            # If conversation_id is provided, check if it exists
            if conversation_id:
                existing_conv = await self.conversations_service.get_conversation(conversation_id)
                if existing_conv:
                    logger.debug(f"Using existing conversation: {conversation_id}")
                    return conversation_id
                else:
                    logger.info(f"Conversation {conversation_id} not found, creating new one")
            
            # Create new conversation
            new_conversation_id = await self.conversations_service.create_conversation(
                user_id=user_id,
                status="active",
                client_info=client_info
            )
            
            if new_conversation_id:
                logger.info(f"Created new conversation: {new_conversation_id} for user: {user_id}")
                return new_conversation_id
            else:
                logger.error(f"Failed to create conversation for user: {user_id}")
                raise Exception("Failed to create conversation")
                
        except Exception as e:
            logger.error(f"Error in get_or_create_conversation: {e}", exc_info=True)
            raise
    
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
        Save a user message to the messages collection.
        
        Args:
            conversation_id: Conversation identifier
            user_id: User identifier
            content: Message content
            message_type: Type of message (text, voice, image)
            user_request: Additional user request data
            input_tokens: Number of input tokens for this user message (optional)
            timestamp: Message timestamp (defaults to now)
            
        Returns:
            Message ID if successful, None otherwise
        """
        try:
            message_id = await self.messages_service.save_user_message(
                conversation_id=conversation_id,
                user_id=user_id,
                content=content,
                message_type=message_type,
                user_request=user_request,
                input_tokens=input_tokens,
                timestamp=timestamp
            )
            
            if message_id:
                # Update conversation's lastMessageAt and increment messageCount
                await self.conversations_service.increment_message_count(
                    conversation_id=conversation_id,
                    update_last_message=True
                )
                logger.debug(f"Saved user message: {message_id} in conversation: {conversation_id}")
            else:
                logger.error(f"Failed to save user message in conversation: {conversation_id}")
            
            return message_id
            
        except Exception as e:
            logger.error(f"Error saving user message: {e}", exc_info=True)
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
        Save an assistant message to the messages collection.

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
            message_id = await self.messages_service.save_assistant_message(
                conversation_id=conversation_id,
                user_id=user_id,
                content=content,
                intent=intent,
                assistant_response=assistant_response,
                agent_card=agent_card,
                suggested_agents=suggested_agents,
                quick_actions=quick_actions,
                analytics_data=analytics_data,
                processing=processing,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                notice=notice,
                timestamp=timestamp
            )
            
            if message_id:
                # Update conversation's lastMessageAt and increment messageCount
                await self.conversations_service.increment_message_count(
                    conversation_id=conversation_id,
                    update_last_message=True
                )
                logger.debug(f"Saved assistant message: {message_id} in conversation: {conversation_id}")
            else:
                logger.error(f"Failed to save assistant message in conversation: {conversation_id}")
            
            return message_id
            
        except Exception as e:
            logger.error(f"Error saving assistant message: {e}", exc_info=True)
            return None
    
    async def get_conversation_messages(
        self,
        conversation_id: str,
        limit: int = 50,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get all messages for a conversation.
        
        Args:
            conversation_id: Conversation identifier
            limit: Maximum number of messages to return
            skip: Number of messages to skip
            
        Returns:
            List of message documents
        """
        try:
            messages = await self.messages_service.get_conversation_messages(
                conversation_id=conversation_id,
                limit=limit,
                skip=skip
            )
            logger.debug(f"Retrieved {len(messages)} messages for conversation: {conversation_id}")
            return messages
        except Exception as e:
            logger.error(f"Error retrieving messages: {e}", exc_info=True)
            return []


# Global instance (singleton pattern)
_conversation_storage: Optional[ConversationStorage] = None


def get_conversation_storage() -> ConversationStorage:
    """Get or create ConversationStorage service instance."""
    global _conversation_storage
    if _conversation_storage is None:
        _conversation_storage = ConversationStorage()
    return _conversation_storage

