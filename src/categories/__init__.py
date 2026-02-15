"""
Categories module for organizing chatbot functionality by category.

Each category handles a specific domain of e-commerce functionality:
- Product Detail: Information about agents, company, subscription, pricing
- Order Management: Order processing, tracking, fulfillment
- Inventory Management: Stock levels, inventory tracking, reorder points
- Customer Support: Support tickets, troubleshooting, account issues
- Analytics & Reporting: Sales analytics, performance reports, insights
- Marketing & Promotions: Campaigns, promotions, advertising strategies
- AI Content Generation: AI-driven tasks including content generation, image analysis, product intelligence
- Recommendation Engine: Recommendations, advice, and improvements based on conversation history
- Insights KB: Product category exploration and category insights
- Out-of-Scope: Queries not related to e-commerce (casual chat, general knowledge, off-topic)
"""
from src.categories.base_category import BaseCategory
from src.categories.product_detail import ProductDetailCategory
from src.categories.analytics_reporting import AnalyticsReportingCategory
from src.categories.recommendation_engine import RecommendationEngineCategory
from src.categories.insights_kb import InsightsKbCategory
from src.categories.out_of_scope import OutOfScopeCategory

__all__ = [
    'BaseCategory',
    'ProductDetailCategory',
    'AnalyticsReportingCategory',
    'RecommendationEngineCategory',
    'InsightsKbCategory',
    'OutOfScopeCategory',
]

