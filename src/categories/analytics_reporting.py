"""
Analytics & Reporting Category

Handles queries about:
- Sales analytics
- Performance reports
- Dashboard metrics
- Data insights
- Business intelligence
"""
from typing import Dict, Optional, List, Any
import httpx
from src.categories.base_category import BaseCategory
from utils.logger_config import get_logger

logger = get_logger(__name__)

# Analytics API endpoint from QUICK_REFERENCE.md
ANALYTICS_API_URL = "https://ai-dev.mysellercentral.com/nlp-agents/api/chat"


class AnalyticsReportingCategory(BaseCategory):
    """
    Analytics & Reporting Category
    
    Handles all queries related to analytics and reporting functionality.
    Calls the external analytics API to process queries.
    """
    
    def __init__(self):
        """Initialize Analytics & Reporting category."""
        super().__init__(
            category_name="Analytics & Reporting",
            category_id="analytics_reporting"
        )
        logger.info("AnalyticsReportingCategory initialized")
    
    def can_handle(self, user_message: str, intent: Optional[str] = None) -> bool:
        """
        Determine if this category can handle the query.
        
        Analytics & Reporting handles queries about reports, analytics, metrics.
        """
        user_lower = user_message.lower()
        
        analytics_keywords = [
            "analytics", "report", "dashboard", "metrics",
            "insights", "performance", "sales data", "statistics"
        ]
        
        return any(keyword in user_lower for keyword in analytics_keywords)
    
    async def process_query(
        self,
        user_message: str,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process an analytics & reporting query by calling the external analytics API.
        
        Args:
            user_message: User's query message
            chat_history: Previous conversation messages (not used for analytics API)
            context: Additional context including user_id and required schema_name
            
        Returns:
            Dict with reply, intent, agentId, token counts, and category
        """
        logger.info(f"AnalyticsReportingCategory received query: {user_message[:100]}...")
        
        try:
            # Get user_id from context, with fallback to default
            user_id = None
            if context:
                user_id = context.get("user_id") or context.get("userId")
            
            # Convert to int if it's a string
            if user_id and isinstance(user_id, str):
                try:
                    user_id = int(user_id)
                except ValueError:
                    logger.warning(f"Could not convert user_id '{user_id}' to integer, using default")
                    user_id = None
            
            # Default user_id if not provided (from QUICK_REFERENCE.md example)
            if not user_id:
                user_id = 48
                logger.warning(f"user_id not found in context, using default: {user_id}")
            else:
                logger.info(f"Using user_id from context: {user_id}")
            
            # Get marketplaces_registered from context
            marketplaces_registered = []
            if context:
                marketplaces_registered = context.get("marketplaces_registered") or []
            
            # Ensure marketplaces_registered is a list
            if not isinstance(marketplaces_registered, list):
                marketplaces_registered = []
            
            # Check if marketplaces_registered is empty - only show message if empty
            if not marketplaces_registered or len(marketplaces_registered) == 0:
                logger.warning(f"marketplaces_registered is empty in context - marketplace not linked")
                return {
                    'reply': "Please link your marketplaces to show analytics.",
                    'intent': 'analytics_query',
                    'agentId': None,
                    'input_tokens': 0,
                    'output_tokens': 0,
                    'category': self.category_id
                }
            
            logger.info(f"Using marketplaces_registered: {marketplaces_registered}")
                        
            # Prepare request payload
            # include_data: true ensures full table_data (all rows); otherwise API returns only first 10 rows
            payload = {
                "message": user_message,
                "user_id": user_id,
                "marketplaces_registered": marketplaces_registered,
                "include_data": True,
            }
            
            logger.info(f"Calling analytics API: {ANALYTICS_API_URL}")
            logger.debug(f"Request payload: message={user_message[:50]}..., user_id={user_id}, marketplaces_registered={marketplaces_registered}")
            
            # Make async HTTP request to analytics API
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    ANALYTICS_API_URL,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()  # Raise exception for HTTP errors
                api_response = response.json()
            
            api_success = api_response.get('success', False)
            logger.info(f"Analytics API response received - success: {api_success}")
            
            # Log full response structure for debugging
            if not api_success:
                logger.warning(f"Analytics API returned success=False. Full response: {api_response}")
            
            # Extract message from response
            reply_message = api_response.get("message", "")
            
            # If API returned success=False, check if we should still use the message or provide a better error
            if not api_success:
                if not reply_message:
                    reply_message = "I encountered an issue processing your analytics query. Please try rephrasing your question or contact support if the problem persists."
                    logger.warning("Analytics API returned success=False with no message field")
                else:
                    # Log the error message but still return it to the user
                    logger.warning(f"Analytics API returned success=False with message: {reply_message[:200]}")
            
            if not reply_message:
                logger.warning("No message field in analytics API response")
                reply_message = "I received a response from the analytics engine, but it didn't contain a message."
            
            logger.info(f"Extracted message from analytics API response (length: {len(reply_message)})")
            
            # Extract all analytics data fields from API response
            analytics_data = {
                'visualization': api_response.get('visualization'),
                'generated_sql': api_response.get('generated_sql'),
                'table_data': api_response.get('table_data'),
                'row_count': api_response.get('row_count'),
                'query_executed': api_response.get('query_executed'),
                'domains': api_response.get('domains'),
                'selected_tables': api_response.get('selected_tables'),
                'marketplace': api_response.get('marketplace'),
                'timestamp': api_response.get('timestamp'),
                'error': api_response.get('error'),
                'requires_clarification': api_response.get('requires_clarification')
            }
            
            # Log what analytics data was extracted
            if analytics_data.get('visualization'):
                logger.info(f"Extracted visualization data from analytics API response")
            if analytics_data.get('generated_sql'):
                logger.info(f"Extracted generated SQL from analytics API response")
            if analytics_data.get('table_data'):
                logger.info(f"Extracted table data ({analytics_data.get('row_count', 0)} rows) from analytics API response")
            
            return {
                'reply': reply_message,
                'intent': 'analytics_query',
                'agentId': None,
                'input_tokens': 0,
                'output_tokens': 0,
                'category': self.category_id,
                'analytics_data': analytics_data  # Include all analytics data
            }
            
        except httpx.HTTPStatusError as e:
            error_msg = f"Analytics API returned error status {e.response.status_code}: {e.response.text}"
            logger.error(error_msg, exc_info=True)
            return {
                'reply': f"I encountered an error while fetching analytics data. Please try again later.",
                'intent': 'general_query',
                'agentId': None,
                'input_tokens': 0,
                'output_tokens': 0,
                'category': self.category_id,
                'error': error_msg
            }
        except httpx.TimeoutException:
            error_msg = "Analytics API request timed out"
            logger.error(error_msg, exc_info=True)
            return {
                'reply': "The analytics service is taking too long to respond. Please try again later.",
                'intent': 'general_query',
                'agentId': None,
                'input_tokens': 0,
                'output_tokens': 0,
                'category': self.category_id,
                'error': error_msg
            }
        except httpx.RequestError as e:
            error_msg = f"Failed to connect to analytics API: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'reply': "I couldn't connect to the analytics service. Please check your connection and try again.",
                'intent': 'general_query',
                'agentId': None,
                'input_tokens': 0,
                'output_tokens': 0,
                'category': self.category_id,
                'error': error_msg
            }
        except Exception as e:
            error_msg = f"Unexpected error in AnalyticsReportingCategory: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'reply': "I encountered an unexpected error while processing your analytics query. Please try again.",
                'intent': 'general_query',
                'agentId': None,
                'input_tokens': 0,
                'output_tokens': 0,
                'category': self.category_id,
                'error': error_msg
            }

