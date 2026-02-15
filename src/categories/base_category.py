"""
Base class for all category handlers.

Provides common attributes (category_name, category_id) used by category
implementations when building responses.
"""
from typing import Dict, Optional, List, Any


class BaseCategory:
    """
    Base class for category handlers.

    Subclasses must implement can_handle() and process_query().
    """

    def __init__(self, category_name: str, category_id: str):
        self.category_name = category_name
        self.category_id = category_id

    def can_handle(self, user_message: str, intent: Optional[str] = None) -> bool:
        """Determine if this category can handle the query. Override in subclasses."""
        return False

    async def process_query(
        self,
        user_message: str,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Process the query. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement process_query()")
