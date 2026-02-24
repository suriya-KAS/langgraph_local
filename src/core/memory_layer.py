"""
Memory Layer for Conversation Context Management

This module handles conversation memory by:
1. For messages <= 4: Returns last 4 messages as context
2. At message 4: Summarizes messages 1-4 using LLM
3. At message 8: Summarizes messages 5-8 using LLM
4. At message 12: Summarizes messages 9-12 using LLM
5. And so on for every multiple of 4 messages
6. For context: Uses all relevant summaries + recent messages (last 4)
"""
import os
import sys
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import json

# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger_config import get_logger
from src.database.conversation_service import get_conversation_service
from database.schema.messages import get_mongodb_service
from src.core.backend import invoke_gemini_with_tokens
from dotenv import load_dotenv

load_dotenv()

logger = get_logger(__name__)


def get_summary_chunk_key(start_index: int, end_index: int) -> str:
    """
    Generate a unique key for a summary chunk.
    
    Args:
        start_index: Starting message index (1-based)
        end_index: Ending message index (1-based)
        
    Returns:
        String key like "1-4" or "5-8"
    """
    return f"{start_index}-{end_index}"


async def summarize_messages(messages: List[Dict[str, Any]]) -> Optional[str]:
    """
    Summarize a list of messages using LLM.
    
    Args:
        messages: List of message dictionaries with 'role' and 'content' fields
        
    Returns:
        Summary string if successful, None otherwise
    """
    try:
        logger.info(f"Summarizing {len(messages)} messages using LLM")
        
        # Format messages for summarization
        conversation_text = ""
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("processingContent") or msg.get("content", "")
            conversation_text += f"{role.capitalize()}: {content}\n\n"
        
        # Create e-commerce focused summarization prompt
        system_prompt = """You are a memory assistant for an e-commerce seller support chatbot. Your task is to extract and remember key facts and important information from conversations.

Focus on capturing:
- Important facts, numbers, and specific details mentioned
- User's context, goals, and pain points
- Advertising metrics, performance data, or KPIs discussed
- AI agents or tools mentioned by name
- Keywords, optimization strategies, or SEO tips shared
- Pricing, costs, or financial information
- Any specific targets, percentages, or thresholds
- Products, categories, or business context

Write naturally as if remembering key facts - no need for structured formatting. Preserve exact terms, numbers, and percentages as mentioned. Be concise but comprehensive."""
        
        user_prompt = f"""Extract and remember the key facts and important information from this conversation. Focus on what matters most for future context.

Conversation:
{conversation_text}"""
        
        # Format messages for Gemini
        formatted_messages = [{
            "role": "user",
            "content": user_prompt
        }]
        
        # Invoke Gemini for summarization (run in executor to avoid blocking event loop)
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        def _summarize():
            return invoke_gemini_with_tokens(
                formatted_messages=formatted_messages,
                system_prompt=system_prompt,
                max_tokens=700,
                temperature=0.1,
            )
        
        summary, _, _ = await loop.run_in_executor(None, _summarize)
        
        logger.info(f"Successfully generated summary (length: {len(summary)} characters)")
        return summary.strip()
        
    except Exception as e:
        logger.error(f"Error summarizing messages: {e}", exc_info=True)
        return None


def get_required_summaries(message_count: int) -> List[Dict[str, int]]:
    """
    Calculate which summary chunks should exist based on message count.
    
    Summaries are created for chunks:
    - Messages 1-4 (created at message 4)
    - Messages 5-8 (created at message 8)
    - Messages 9-12 (created at message 12)
    - And so on for every multiple of 4
    
    Args:
        message_count: Total number of messages in conversation
        
    Returns:
        List of summary chunk dictionaries with startIndex and endIndex
        Example: [{"startIndex": 1, "endIndex": 4}, {"startIndex": 5, "endIndex": 8}]
    """
    required = []
    chunk_size = 4
    
    # Calculate completed chunks (multiples of 4)
    for i in range(chunk_size, message_count + 1, chunk_size):
        start_index = i - chunk_size + 1  # 1-based indexing
        end_index = i
        required.append({
            "startIndex": start_index,
            "endIndex": end_index
        })
    
    return required


async def create_summary_for_chunk(
    conversation_id: str,
    start_index: int,
    end_index: int,
    messages: List[Dict[str, Any]]
) -> Optional[str]:
    """
    Create a summary for a specific message chunk and save it.
    
    Args:
        conversation_id: The conversation ID
        start_index: Starting message index (1-based)
        end_index: Ending message index (1-based)
        messages: List of messages for this chunk (should be 4 messages)
        
    Returns:
        Summary string if successful, None otherwise
    """
    try:
        logger.info(f"Creating summary for messages {start_index}-{end_index}")
        
        # Summarize the messages
        summary = await summarize_messages(messages)
        if not summary:
            logger.warning(f"Failed to generate summary for messages {start_index}-{end_index}")
            return None
        
        # Get conversation service
        conversation_service = get_conversation_service()
        
        # Get existing summaries or create new array
        conversation = conversation_service.get_conversation(conversation_id)
        if not conversation:
            logger.error(f"Conversation not found: {conversation_id}")
            return None
        
        existing_summaries = conversation.get("conversationSummaries", [])
        
        # Create new summary object
        summary_obj = {
            "summary": summary,
            "startIndex": start_index,
            "endIndex": end_index,
            "messageCount": end_index - start_index + 1,
            "createdAt": datetime.now(timezone.utc)
        }
        
        # Check if summary for this chunk already exists
        chunk_key = get_summary_chunk_key(start_index, end_index)
        updated = False
        for i, existing in enumerate(existing_summaries):
            if existing.get("startIndex") == start_index and existing.get("endIndex") == end_index:
                # Update existing summary
                existing_summaries[i] = summary_obj
                updated = True
                break
        
        if not updated:
            # Add new summary
            existing_summaries.append(summary_obj)
        
        # Sort summaries by startIndex
        existing_summaries.sort(key=lambda x: x.get("startIndex", 0))
        
        # Update conversation with summaries array
        conversation_service.update_conversation(
            conversation_id=conversation_id,
            conversation_summaries=existing_summaries
        )
        
        logger.info(f"Successfully saved summary for messages {start_index}-{end_index}")
        return summary
        
    except Exception as e:
        logger.error(f"Error creating summary for chunk {start_index}-{end_index}: {e}", exc_info=True)
        return None


async def get_conversation_context(conversation_id: str, current_user_message: str) -> List[Dict[str, Any]]:
    """
    Get conversation context based on message count and memory management rules.
    
    Memory Management Logic:
    1. If message count <= 4: Return last 4 messages (or all if less than 4)
    2. At message 4: Summarize messages 1-4
    3. At message 8: Summarize messages 5-8
    4. At message 12: Summarize messages 9-12
    5. And so on for every multiple of 4 messages
    6. For context retrieval:
       - Messages 1-4: Return all messages
       - Messages 5-8: Return summary(1-4) + messages 5-8
       - Messages 9-12: Return summary(1-4) + summary(5-8) + messages 9-12
       - Messages 13+: Return all summaries + last 4 messages
    
    Args:
        conversation_id: The conversation ID
        current_user_message: The current user message (not included in context)
        
    Returns:
        List of message dictionaries formatted for LLM context
        Format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    """
    try:
        logger.info(f"Getting conversation context for conversation: {conversation_id}")
        
        # Get conversation service and messages service
        conversation_service = get_conversation_service()
        messages_service = get_mongodb_service()
        
        # Get conversation document
        conversation = conversation_service.get_conversation(conversation_id)
        if not conversation:
            logger.warning(f"Conversation not found: {conversation_id}")
            return []
        
        # Get message count
        message_count = conversation.get("stats", {}).get("messageCount", 0)
        logger.info(f"Conversation message count: {message_count}")
        
        # Get existing summaries
        conversation_summaries = conversation.get("conversationSummaries", [])
        # Legacy support: check for old single summary format
        if not conversation_summaries:
            legacy_summary = conversation.get("conversationSummary")
            if legacy_summary and legacy_summary.get("summary"):
                # Migrate old format to new format
                conversation_summaries = [{
                    "summary": legacy_summary.get("summary"),
                    "startIndex": 1,
                    "endIndex": 4,
                    "messageCount": 4,
                    "createdAt": legacy_summary.get("createdAt", datetime.now(timezone.utc))
                }]
        
        # Step 1: Check what summaries should exist and create missing ones
        # Only create summaries for completed chunks (multiples of 4)
        all_messages = await messages_service.get_conversation_messages(conversation_id)
        
        # Check which summaries exist
        existing_summary_keys = set()
        for summary in conversation_summaries:
            start_idx = summary.get("startIndex")
            end_idx = summary.get("endIndex")
            if start_idx and end_idx:
                existing_summary_keys.add(get_summary_chunk_key(start_idx, end_idx))
        
        # Create missing summaries for completed chunks
        # Chunks are completed when message count is a multiple of 4
        chunk_size = 4
        completed_chunks = (message_count // chunk_size) * chunk_size
        
        if completed_chunks >= chunk_size:
            for chunk_end in range(chunk_size, completed_chunks + 1, chunk_size):
                start_idx = chunk_end - chunk_size + 1  # 1-based
                end_idx = chunk_end
                chunk_key = get_summary_chunk_key(start_idx, end_idx)
                
                # Check if summary exists for this completed chunk
                if chunk_key not in existing_summary_keys:
                    # Get messages for this chunk (convert to 0-based indexing)
                    chunk_messages = all_messages[start_idx - 1:end_idx] if len(all_messages) >= end_idx else []
                    
                    if len(chunk_messages) == chunk_size:
                        logger.info(f"Creating missing summary for completed chunk {start_idx}-{end_idx}")
                        await create_summary_for_chunk(
                            conversation_id=conversation_id,
                            start_index=start_idx,
                            end_index=end_idx,
                            messages=chunk_messages
                        )
        
        # Refresh conversation to get updated summaries
        conversation = conversation_service.get_conversation(conversation_id)
        conversation_summaries = conversation.get("conversationSummaries", [])
        
        # Step 2: Build context based on message count
        # Case 1: Message count <= 4 - return all messages
        if message_count <= 4:
            logger.info(f"Message count <= 4, returning all {message_count} messages")
            
            context_messages = []
            for msg in all_messages:
                role = msg.get("role", "unknown")
                # For user messages from quick actions, processingContent has the
                # actual message with IDs (e.g. category IDs) while content has the
                # human-readable display text. The LLM needs the processing version
                # to resolve follow-up references like "and description analysis?".
                content = msg.get("processingContent") or msg.get("content", "")
                if role in ["user", "assistant"] and content:
                    context_messages.append({
                        "role": role,
                        "content": content
                    })
            
            logger.info(f"Returning {len(context_messages)} messages (all messages for count <= 4)")
            return context_messages
        
        # Case 2: Message count > 4 - use summaries + recent messages
        logger.info(f"Message count is {message_count} (> 4), using summaries + recent messages")
        
        # Sort summaries by startIndex
        conversation_summaries.sort(key=lambda x: x.get("startIndex", 0))
        
        # Determine the last completed chunk index
        last_completed_chunk_end = 0
        for summary in conversation_summaries:
            end_idx = summary.get("endIndex", 0)
            if end_idx > last_completed_chunk_end:
                last_completed_chunk_end = end_idx
        
        # Build context messages
        context_messages = []
        
        # Add all existing summaries
        for summary in conversation_summaries:
            start_idx = summary.get("startIndex", 0)
            end_idx = summary.get("endIndex", 0)
            summary_text = summary.get("summary", "")
            
            if summary_text:
                context_messages.append({
                    "role": "user",
                    "content": f"[Previous conversation summary (messages {start_idx}-{end_idx})]: {summary_text}"
                })
        
        # Get recent messages (messages after the last completed chunk)
        if last_completed_chunk_end > 0:
            # Messages after the last completed summary chunk
            recent_messages = all_messages[last_completed_chunk_end:] if len(all_messages) > last_completed_chunk_end else []
        else:
            # No summaries yet, use all messages (shouldn't happen for count > 4, but fallback)
            recent_messages = all_messages
        
        # Limit recent messages to last 4
        if len(recent_messages) > 4:
            recent_messages = recent_messages[-4:]
        
        # Add recent messages to context
        for msg in recent_messages:
            role = msg.get("role", "unknown")
            content = msg.get("processingContent") or msg.get("content", "")
            if role in ["user", "assistant"] and content:
                context_messages.append({
                    "role": role,
                    "content": content
                })
        
        summaries_count = len([s for s in conversation_summaries if s.get("summary")])
        logger.info(f"Returning {summaries_count} summaries + {len(recent_messages)} recent messages")
        return context_messages
        
    except Exception as e:
        logger.error(f"Error getting conversation context: {e}", exc_info=True)
        return []


class MemoryLayer:
    """
    Memory Layer class for managing conversation context.
    
    This class provides an interface for the API to retrieve formatted chat history
    with automatic memory management (summarization, context windowing).
    """
    
    def __init__(self):
        """Initialize the memory layer."""
        logger.info("MemoryLayer initialized")
    
    async def get_formatted_chat_history_for_backend(
        self, 
        conversation_id: str,
        current_message: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Get formatted chat history for the backend LLM.
        
        This method retrieves the conversation context using the memory management rules:
        - For messages <= 4: Returns all messages
        - At message 4: Creates summary for messages 1-4
        - At message 8: Creates summary for messages 5-8
        - At message 12: Creates summary for messages 9-12
        - And so on for every multiple of 4 messages
        - For messages > 4: Returns all relevant summaries + recent messages (last 4)
        
        Args:
            conversation_id: The conversation ID
            current_message: The current user message (optional, for context)
            
        Returns:
            List of message dictionaries formatted for LLM:
            [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        """
        try:
            logger.info(f"MemoryLayer: Getting formatted chat history for conversation: {conversation_id}")
            
            # Use the get_conversation_context function
            context_messages = await get_conversation_context(
                conversation_id=conversation_id,
                current_user_message=current_message
            )
            
            logger.info(f"MemoryLayer: Returning {len(context_messages)} messages for conversation: {conversation_id}")
            return context_messages
            
        except Exception as e:
            logger.error(f"MemoryLayer: Error getting chat history: {e}", exc_info=True)
            return []
    
    async def get_context_with_summary(self, conversation_id: str) -> Dict[str, Any]:
        """
        Get conversation context along with summary information.
        
        Returns:
            Dictionary containing:
            - messages: List of context messages
            - has_summaries: Whether summaries were used
            - summaries_count: Number of summaries available
            - message_count: Total message count in conversation
            - summaries: List of summary objects
        """
        try:
            conversation_service = get_conversation_service()
            conversation = conversation_service.get_conversation(conversation_id)
            
            if not conversation:
                return {
                    "messages": [],
                    "has_summaries": False,
                    "summaries_count": 0,
                    "message_count": 0,
                    "summaries": []
                }
            
            message_count = conversation.get("stats", {}).get("messageCount", 0)
            conversation_summaries = conversation.get("conversationSummaries", [])
            
            # Legacy support
            if not conversation_summaries:
                legacy_summary = conversation.get("conversationSummary")
                if legacy_summary and legacy_summary.get("summary"):
                    conversation_summaries = [{
                        "summary": legacy_summary.get("summary"),
                        "startIndex": 1,
                        "endIndex": 4,
                        "messageCount": 4
                    }]
            
            has_summaries = len(conversation_summaries) > 0
            
            context_messages = await get_conversation_context(conversation_id, "")
            
            return {
                "messages": context_messages,
                "has_summaries": has_summaries,
                "summaries_count": len(conversation_summaries),
                "message_count": message_count,
                "summaries": conversation_summaries
            }
            
        except Exception as e:
            logger.error(f"Error getting context with summary: {e}", exc_info=True)
            return {
                "messages": [],
                "has_summaries": False,
                "summaries_count": 0,
                "message_count": 0,
                "summaries": []
            }


# Singleton instance
_memory_layer: Optional[MemoryLayer] = None


def get_memory_layer() -> MemoryLayer:
    """
    Get or create the MemoryLayer singleton instance.
    
    Returns:
        MemoryLayer instance
    """
    global _memory_layer
    if _memory_layer is None:
        _memory_layer = MemoryLayer()
    return _memory_layer