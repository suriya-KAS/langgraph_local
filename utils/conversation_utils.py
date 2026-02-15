"""
Utility functions for conversation management
"""
import secrets


def generate_conversation_id_safe(user_id: str) -> str:
    """
    Generate a conversation ID following the schema pattern: conv_[16 hex chars]
    
    Uses secrets.token_hex(8) which generates 16 hex characters (128 bits of randomness).
    This provides 2^128 possible values, which is cryptographically secure and 
    sufficient for production use. Matches MongoDB schema pattern: ^conv_[a-f0-9]{16}$
    
    Args:
        user_id: User identifier (not used in ID generation, kept for API compatibility)
        
    Returns:
        Conversation ID in format: conv_{16 hex chars}
    """
    # Format: conv_{16 hex chars} - matches schema pattern ^conv_[a-f0-9]{16}$
    return f"conv_{secrets.token_hex(8)}"

