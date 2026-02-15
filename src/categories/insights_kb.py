"""
Insights KB Category

Handles queries about product categories and category insights:
- Exploring a product category (Electronics, Laptops, Fashion, etc.)
- Category-level insights and discovery
"""
from typing import Dict, Optional, List, Any
from src.categories.base_category import BaseCategory
from utils.logger_config import get_logger

logger = get_logger(__name__)


class InsightsKbCategory(BaseCategory):
    """
    Insights KB Category.

    Handles queries where the user asks about or explores a product category.
    """

    def __init__(self):
        """Initialize Insights KB category."""
        super().__init__(
            category_name="Insights KB",
            category_id="insights_kb"
        )
        logger.info("InsightsKbCategory initialized")

    def can_handle(self, user_message: str, intent: Optional[str] = None) -> bool:
        """
        Determine if this category can handle the query.
        Classification is done by the orchestrator LLM; this is a fallback check.
        """
        user_lower = user_message.lower()
        category_keywords = [
            "electronics", "laptops", "fashion", "footwear", "kitchen",
            "gaming", "category", "categories", "insights", "explore"
        ]
        return any(kw in user_lower for kw in category_keywords)

    async def process_query(
        self,
        user_message: str,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process an insights KB query (category exploration / insights).

        Args:
            user_message: User's query message
            chat_history: Previous conversation messages
            context: Additional context (may include asins from orchestrator)

        Returns:
            Dict with reply, intent, agentId, token counts, category, and asins if any
        """
        logger.info(f"InsightsKbCategory received query: {user_message[:100]}...")
        asins = context.get("asins", []) if context else []

        # Placeholder reply; integrate with ASIN DB service as needed (see src.services.asin_db_connector)
        reply = (
            "I can help you explore product categories and insights. "
            "Share the category you're interested in (e.g. Electronics, Laptops, Fashion), "
            "or ask for insights on a specific product."
        )

        result = {
            "reply": reply,
            "intent": "insights_kb",
            "agentId": None,
            "input_tokens": 0,
            "output_tokens": 0,
            "category": self.category_id,
        }
        if asins:
            result["asins"] = asins
        return result
