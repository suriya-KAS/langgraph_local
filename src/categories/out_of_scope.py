"""
Out-of-Scope Category

Handles queries that are not related to e-commerce business operations:
- Casual chit-chat
- General knowledge questions
- Non-e-commerce advice
- Current events & news
- Account management commands
- Technical off-topic questions
"""
from typing import Dict, Optional, List, Any
from src.categories.base_category import BaseCategory
from utils.logger_config import get_logger

logger = get_logger(__name__)


class OutOfScopeCategory(BaseCategory):
    """
    Out-of-Scope Category
    
    Handles queries that are outside the scope of e-commerce business operations.
    Politely declines and redirects users to e-commerce-related topics.
    """
    
    def __init__(self):
        """Initialize Out-of-Scope category."""
        super().__init__(
            category_name="Out-of-Scope",
            category_id="out_of_scope"
        )
        logger.info("OutOfScopeCategory initialized")
    
    def can_handle(self, user_message: str, intent: Optional[str] = None) -> bool:
        """
        Determine if this category can handle the query.
        
        Out-of-Scope handles queries that are not related to e-commerce operations.
        This is a fallback category - other categories should be checked first.
        """
        user_lower = user_message.lower()
        
        # Out-of-scope indicators (but this should be determined by LLM classification first)
        out_of_scope_keywords = [
            "weather", "weekend", "world cup", "recipe", "faucet",
            "delete account", "python code", "debug", "news", "current events"
        ]
        
        return any(keyword in user_lower for keyword in out_of_scope_keywords)
    
    async def process_query(
        self,
        user_message: str,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process an out-of-scope query.
        
        Politely declines to answer and redirects to e-commerce topics.
        
        Args:
            user_message: User's query message
            chat_history: Previous conversation messages
            context: Additional context (user_id, language, username, etc.)
            
        Returns:
            Dict with reply, intent, agentId, token counts, and category
        """
        logger.info(f"OutOfScopeCategory received query: {user_message[:100]}...")
        
        # Get username from context if available
        username = context.get("username", "") if context else ""
        greeting = f"Hi {username}! " if username else "Hi! "
        
        # Polite decline message
        reply = (
            f"{greeting}I'm specifically designed to help with e-commerce business operations. "
            f"I can't assist with that topic, but I'd be happy to help you with:\n\n"
            f"• **Listing Optimization** - Generate titles, bullet points, descriptions, A+ content\n"
            f"• **Analytics & Reporting** - Sales data, ad performance, inventory levels\n"
            f"• **Market Intelligence** - Competitor analysis, pricing intelligence, best practices\n"
            f"• **Product Support** - Platform features, account setup, integrations\n\n"
            f"What would you like to know about your e-commerce business?"
        )
        
        logger.info(f"Out-of-scope query handled with polite decline")
        
        return {
            'reply': reply,
            'intent': 'out_of_scope',
            'agentId': None,
            'input_tokens': 0,
            'output_tokens': 0,
            'category': self.category_id
        }

