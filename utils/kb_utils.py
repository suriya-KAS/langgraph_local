"""
Knowledge Base utility functions for consistent KB ID retrieval from environment variables.
"""
import os
from utils.logger_config import get_logger

logger = get_logger(__name__)


def get_knowledge_base_id() -> str:
    """
    Get Knowledge Base ID from environment variables.
    
    Checks in order:
    1. KNOWLEDGE_BASE_ID
    2. BEDROCK_KNOWLEDGE_BASE_ID
    
    Raises:
        ValueError: If neither environment variable is set
    
    Returns:
        str: Knowledge Base ID
    """
    kb_id = os.getenv('KNOWLEDGE_BASE_ID') or os.getenv('BEDROCK_KNOWLEDGE_BASE_ID')
    
    if not kb_id:
        error_msg = (
            "Knowledge Base ID not found in environment variables. "
            "Please set either KNOWLEDGE_BASE_ID or BEDROCK_KNOWLEDGE_BASE_ID in your .env file."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    logger.debug(f"Using Knowledge Base ID: {kb_id} (from {'KNOWLEDGE_BASE_ID' if os.getenv('KNOWLEDGE_BASE_ID') else 'BEDROCK_KNOWLEDGE_BASE_ID'})")
    return kb_id
