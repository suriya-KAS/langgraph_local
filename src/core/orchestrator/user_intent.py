"""
User Intent Finder and Query Router

This module serves as the orchestrator that:
1. Finds the intent of user queries (product_detail, analytics_reporting, insights_kb, or out_of_scope)
2. Extracts ASIN(s) and category name (product/topic category) from the query as separate entities for reuse by other components
3. Routes queries to the appropriate category handler:
   - product_detail → ProductDetailCategory
   - analytics_reporting → AnalyticsReportingCategory
   - insights_kb → InsightsKbCategory
   - out_of_scope → OutOfScopeCategory

The intent classification is done using an LLM to determine which category
should handle the user's query.
"""
from typing import Dict, Optional, List, Any, Tuple
import asyncio
import json
import re
from langfuse import get_client, observe
from utils.logger_config import get_logger

from src.core.asin_validator import validate_asins_for_client, get_client_asins
from src.services.mp_validator import validate_from_context
from src.core.orchestrator.work_status import finalize_enriched_query
# from src.core.long_term_memory import enrich_query_with_ltm_context  # Disabled for production

# Import all categories
from src.categories.product_detail import ProductDetailCategory
from src.categories.analytics_reporting import AnalyticsReportingCategory
from src.categories.insights_kb import InsightsKbCategory
from src.categories.out_of_scope import OutOfScopeCategory

# Import LLM functions from backend (Gemini)
from src.core.backend import invoke_gemini_with_tokens

logger = get_logger(__name__)


class Orchestrator:
    """
    User Intent Finder and Query Router
    
    This orchestrator:
    1. Uses LLM to classify user queries into intent categories:
       - product_detail: Questions about platform features, capabilities, pricing, integrations, AND recommendations/advice about business performance
       - analytics_reporting: Questions about user's own data, metrics, reports, analytics
       - insights_kb: Questions about product categories to explore or category insights
       - out_of_scope: Queries not related to e-commerce (casual chat, general knowledge, off-topic)
    2. Extracts ASIN(s) from the user query as a separate entity (for reuse by other components).
    3. Routes queries to the appropriate category handler:
       - product_detail → ProductDetailCategory (handles product/feature questions and recommendations/advice)
       - analytics_reporting → AnalyticsReportingCategory (handles user's own analytics/reporting questions)
       - insights_kb → InsightsKbCategory (handles category exploration and insights)
       - out_of_scope → OutOfScopeCategory (handles non-e-commerce queries with polite decline)
    4. Returns the category's processed response
    """
    
    def __init__(self):
        """Initialize the orchestrator with all available categories."""
        logger.info("Initializing Orchestrator")
        
        # Initialize categories (product_detail, analytics_reporting, insights_kb, out_of_scope)
        self.categories = {
            "product_detail": ProductDetailCategory(),
            "analytics_reporting": AnalyticsReportingCategory(),
            "insights_kb": InsightsKbCategory(),
            "out_of_scope": OutOfScopeCategory(),
        }
        
        # Available categories for LLM classification
        self.available_categories = ["product_detail", "analytics_reporting", "insights_kb", "out_of_scope"]
        
        logger.info(f"Orchestrator initialized with {len(self.categories)} categories")
        logger.info(f"LLM classification enabled for categories: {self.available_categories}")
        for cat_id, category in self.categories.items():
            logger.info(f"  - {category.category_name} ({cat_id})")

    # Known marketplace API identifiers (lowercase) for extraction from user query
    _MARKETPLACE_PATTERNS = [
        "amazon.com", "amazon.in", "amazon.co.uk", "amazon.ca", "amazon.com.mx", "amazon.ae",
        "vendorcentral.amazon.com", "www.vendorcentral.in",
        "flipkart.com", "walmart.com", "shopify.com", "ebay.com",
    ]

    @observe(name="extract_marketplace_from_text")
    def _extract_marketplace_from_text(self, text: str) -> Optional[str]:
        """
        Extract a marketplace mentioned in the user's message (e.g. 'on Amazon.com', 'for amazon.in').
        Returns the API-format marketplace string (lowercase) or None if none found.
        """
        if not text or not text.strip():
            return None
        lower = text.lower()
        # Prefer longer matches first (e.g. amazon.com before amazon)
        for mp in sorted(self._MARKETPLACE_PATTERNS, key=len, reverse=True):
            if mp in lower:
                return mp
        return None

    @observe(name="parse_classification_response")
    def _parse_classification_response(self, response: str, original_message: str) -> Tuple[Optional[str], str, List[str], Optional[str], Optional[str], Optional[str], Optional[str], bool]:
        """
        Parse category, enriched_query, asins, category_name, query_category_id, marketplace_from_query, user_needs, and requires_long_term_memory from LLM JSON response.

        Args:
            response: LLM response text
            original_message: Original user message (fallback for enriched_query)

        Returns:
            Tuple of (category_id, enriched_query, asins, category_name, query_category_id, marketplace_from_query, user_needs, requires_long_term_memory).
            asins is a list of ASIN strings.
            category_name is the product/topic category mentioned by the user, or None if not mentioned.
            query_category_id is the numeric category ID (e.g. "1983610031") when user says "category id: X", or None.
            marketplace_from_query is the marketplace explicitly mentioned in the query (e.g. "amazon.com") or None.
            user_needs is a string describing what the user wants (e.g. "title and description analysis", "keyword analysis", "competitor analysis") or None.
        """
        logger.debug("Parsing classification response from LLM")

        def parse_one(parsed: Dict[str, Any]) -> Tuple[Optional[str], str, List[str], Optional[str], Optional[str], Optional[str], Optional[str], bool]:
            category = parsed.get("category")
            enriched = parsed.get("enriched_query", original_message)
            raw_asins = parsed.get("asins")
            if raw_asins is None:
                asins: List[str] = []
            elif isinstance(raw_asins, list):
                asins = [str(a).strip() for a in raw_asins if a]
            else:
                asins = [str(raw_asins).strip()] if raw_asins else []
            raw_category_name = parsed.get("category_name")
            if raw_category_name is None or (isinstance(raw_category_name, str) and not raw_category_name.strip()):
                category_name: Optional[str] = None
            else:
                category_name = str(raw_category_name).strip() or None
            raw_query_cat_id = parsed.get("query_category_id")
            if raw_query_cat_id is None or (isinstance(raw_query_cat_id, str) and not raw_query_cat_id.strip()):
                query_category_id: Optional[str] = None
            else:
                query_category_id = str(raw_query_cat_id).strip() or None
            raw_mp = parsed.get("marketplace_from_query")
            if raw_mp is None or (isinstance(raw_mp, str) and not raw_mp.strip()):
                marketplace_from_query: Optional[str] = None
            else:
                marketplace_from_query = str(raw_mp).strip().lower() or None
            raw_user_needs = parsed.get("user_needs")
            if raw_user_needs is None or (isinstance(raw_user_needs, str) and not raw_user_needs.strip()):
                user_needs: Optional[str] = None
            else:
                user_needs = str(raw_user_needs).strip() or None
            # requires_long_term_memory: true when the query needs prior conversation context to resolve references
            raw_ltm = parsed.get("requires_long_term_memory")
            requires_long_term_memory = bool(raw_ltm) if raw_ltm is not None else False
            if not category or category not in self.available_categories:
                return None, original_message, [], category_name, query_category_id, marketplace_from_query, user_needs, requires_long_term_memory
            return category, enriched, asins, category_name, query_category_id, marketplace_from_query, user_needs, requires_long_term_memory

        # Strategy 1: Look for JSON in markdown code blocks
        json_patterns = [
            r'```json\s*(\{.*?\})\s*```',  # ```json {...} ```
            r'```\s*(\{.*?\})\s*```',      # ``` {...} ```
            r'`(\{.*?\})`',                 # `{...}`
        ]

        for pattern in json_patterns:
            match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
            if match:
                try:
                    parsed = json.loads(match.group(1))
                    category, enriched, asins, category_name, query_category_id, marketplace_from_query, user_needs, requires_long_term_memory = parse_one(parsed)
                    if category:
                        logger.info(f"Successfully parsed - category: {category}, enriched: {enriched[:50]}..., asins: {asins}, category_name: {category_name}, query_category_id: {query_category_id}, marketplace_from_query: {marketplace_from_query}, user_needs: {user_needs}, requires_long_term_memory: {requires_long_term_memory}")
                        return category, enriched, asins, category_name, query_category_id, marketplace_from_query, user_needs, requires_long_term_memory
                except (json.JSONDecodeError, IndexError) as e:
                    logger.debug(f"Failed to parse JSON: {e}")
                    continue

        # Strategy 2: Find JSON object with category field (allow nested braces for richer JSON)
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*"category"[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
        if not json_match:
            json_match = re.search(r'(\{[^{}]*"category"[^{}]*\})', response, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                category, enriched, asins, category_name, query_category_id, marketplace_from_query, user_needs, requires_long_term_memory = parse_one(parsed)
                if category:
                    logger.info(f"Successfully parsed (strategy 2) - category: {category}")
                    return category, enriched, asins, category_name, query_category_id, marketplace_from_query, user_needs, requires_long_term_memory
            except json.JSONDecodeError as e:
                logger.debug(f"Strategy 2 failed to parse JSON: {e}")

        # Strategy 3: Greedy brace match for single JSON object
        brace = response.find("{")
        if brace >= 0:
            depth = 0
            for i, c in enumerate(response[brace:], start=brace):
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            parsed = json.loads(response[brace : i + 1])
                            category, enriched, asins, category_name, query_category_id, marketplace_from_query, user_needs, requires_long_term_memory = parse_one(parsed)
                            if category:
                                logger.info(f"Successfully parsed (strategy 3) - category: {category}")
                                return category, enriched, asins, category_name, query_category_id, marketplace_from_query, user_needs, requires_long_term_memory
                        except json.JSONDecodeError:
                            pass
                        break

        logger.warning("Could not parse classification response from LLM")
        return None, original_message, [], None, None, None, None, False

    @observe(name="find_user_intent", as_type="generation")
    async def find_user_intent(
        self,
        user_message: str,
        intent: Optional[str] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str, List[str], Optional[str], Optional[str], Optional[str], Optional[str], bool]:
        """
        Find the intent/category AND generate enriched query for a user message.

        This method uses an LLM to:
        1. Classify the user's query into a category
        2. Generate an enriched, self-contained version of the query

        The enriched query:
        - Resolves follow-up references (pronouns like "it", "that", short questions)
        - Includes user context (marketplaces) when relevant
        - Is complete and self-contained for downstream processing

        Args:
            user_message: User's query message
            intent: Optional pre-detected intent (not used in LLM classification)
            chat_history: Previous conversation messages for context
            user_context: User context including marketplaces_registered, username, etc.

        Returns:
            Tuple of (category_id, enriched_message, asins, category_name, query_category_id, marketplace_from_query, user_needs, requires_long_term_memory).
            asins is a list of ASIN strings; category_name is the product/topic category, or None;
            query_category_id is the numeric category ID from the query (e.g. "1983610031") when present, or None;
            marketplace_from_query is the marketplace explicitly mentioned in the query (e.g. "amazon.com") or None;
            user_needs is a string describing what the user wants analyzed (e.g. "title and description analysis") or None;
            requires_long_term_memory is True when the query needs prior conversation context to resolve references.
        """
        logger.info(f"Finding intent for user query: {user_message[:100]}...")
        
        # Build conversation context for classification
        conversation_context = "None"
        if chat_history:
            # Include last 3-4 messages for context (to understand references like "it", "that", etc.)
            recent_messages = chat_history[-4:] if len(chat_history) > 4 else chat_history
            context_lines = []
            for msg in recent_messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                if role == "user":
                    # Truncate long messages for context
                    truncated = content[:250] + "..." if len(content) > 250 else content
                    context_lines.append(f"User: {truncated}")
                elif role == "assistant":
                    truncated = content[:250] + "..." if len(content) > 250 else content
                    context_lines.append(f"Assistant: {truncated}")
            
            if context_lines:
                conversation_context = "\n".join(context_lines)
                logger.debug(f"Including {len(recent_messages)} recent messages in classification context")
        
        # Build user context info
        marketplaces = user_context.get("marketplaces_registered", []) if user_context else []
        marketplace_info = ", ".join(marketplaces) if marketplaces else "Not specified"
        wallet_balance = user_context.get("walletBalance") or user_context.get("wallet_balance") if user_context else None
        login_location = user_context.get("loginLocation") or user_context.get("login_location") if user_context else None
        
        # Create combined classification + enrichment prompt
        classification_prompt = f"""You are an e-commerce chatbot query classifier and enricher.

**YOUR TASKS:**
1. Classify the query into ONE category
2. Generate an ENRICHED version of the query that is complete and self-contained
3. ASINs: If the user's query contains any ASIN(s) (Amazon Standard Identification Number — typically 10 alphanumeric characters, e.g. B08N5WRWNW), extract them and list in "asins" as a JSON array. If none, use "asins": []
4. Category name (product/topic): Extract "category_name" ONLY when the user EXPLICITLY mentions a product category or topic (e.g. "wireless earbuds", "kitchen appliances", "smartphones"). Use the user's exact or near-verbatim wording. Do NOT infer, guess, or invent a category. If the user did not mention any category/topic name, set "category_name": null.
5. Category ID (numeric): When the user mentions a numeric category ID (e.g. "category id: 1983610031", "category id 1983610031", "insights for category id 1983610031"), extract that number as a string of digits and set "query_category_id" to it. If none, set "query_category_id": null. This is for insights_kb when users ask for insights by category ID.
6. User needs: Extract "user_needs" ONLY when the user explicitly mentions specific analysis types or needs (e.g. "title analysis", "description analysis", "keyword analysis", "competitor analysis", "title and description analysis", "listing quality analysis"). This should be a concise phrase describing what the user wants analyzed. Use the user's exact or near-verbatim wording. If the user did not mention any specific analysis type, set "user_needs": null. Examples: "i need title and descriptions analysis" → "title and description analysis", "keyword analysis" → "keyword analysis", "competitor analysis, title analysis and keyword analysis" → "competitor analysis, title analysis and keyword analysis".
7. Long-term memory: Set "requires_long_term_memory" to true ONLY when the user's query refers to prior context that must be recalled (e.g. "my top selling ASIN", "that product", "the one we discussed"). Set to false when the user explicitly specifies all needed identifiers (ASINs, category name, category ID) in the current query. Examples: "Get me insights for leather belt category" → false; "What is the ratings of my top selling ASIN?" → true.

**USER CONTEXT (PAYLOAD DATA):**
- Registered marketplaces: {marketplace_info}
- Wallet balance: {wallet_balance if wallet_balance is not None else "Not available"}
- Login location: {login_location if login_location else "Not available"}

**CONVERSATION HISTORY:**
{conversation_context}

**CURRENT QUERY:** {user_message}

**CATEGORIES:**
1. **product_detail**: Platform features, capabilities, pricing, integrations, how-to, identity of the assistant, which agent to use, AND advice/recommendations about USER'S business performance (how to improve, best practices).
   - **IMPORTANT**: Greetings and simple social messages → product_detail (e.g. "Hi", "Hello", "Hey", "Good morning", "Good afternoon", "Thanks", "Thank you", "Bye", "Okay", "Ok"). These are NOT out_of_scope; route them to product_detail so the assistant can respond in a friendly, human way and maintain the connection.
   - "What can you do?", "Do you support X?", "What did I mention earlier?"
   - **IMPORTANT**: Questions about WHO the assistant is → product_detail (e.g. "Who is this?", "Who are you?", "What are you?")
   - **IMPORTANT**: Questions about WHICH AGENT to use for a use case → product_detail (e.g. "I want to improve my sales, which agent do I need?", "My sales are down, which agent should I use?", "Which agent for listing optimization?")
   - **IMPORTANT**: Questions about payload data (marketplaces_registered, walletBalance, loginLocation) should be routed to product_detail
   - **IMPORTANT**: Advice about USER'S business performance (how to improve, best practices) → product_detail (e.g. "How can I improve my sales?", "Best practices for listings?", "What should I do about low revenue?", "How can I improve my business performance?")
   - Examples: "Hi", "Hello", "How many marketplaces did I register?", "What is my wallet balance?", "Who is this?", "Which agent should I use to improve sales?", "How can I improve my sales?", "Best practices for listings?"
   
2. **analytics_reporting**: AGGREGATE metrics and reports from user's OWN data (requires DB queries), including Amazon Ads performance data and ASIN-level transactional metrics.
   - **Sales & Revenue Reporting**: Total sales, best-selling products, quarter-over-quarter comparison
   - **Inventory Analytics**: Products low on stock, total inventory value
   - **Amazon Ads Analytics**: Route ALL Amazon Ads queries here. Any query related to Amazon advertising performance — ad sales, ad spend, ACOS, ROAS, impressions, clicks, campaign performance, or any ad-related metric.
   - Examples: "What is my ad sales this month?", "Show me my ACOS for last 30 days", "Which campaigns are performing best?", "Top performing campaigns on Amazon ads", "What is my total ad spend?", "Compare organic vs ad sales", "Ad sales for my account"
   - **ASIN-Level Transactional Metrics**: When the user asks for numerical/transactional data FOR A SPECIFIC ASIN — including sales, revenue, ad sales, refunds, cancellations, returns, orders — route to analytics_reporting (NOT insights_kb).
   - Examples: "What are the sales for ASIN B08XYZ123?", "Show me refunds for B09ABC456", "Cancellations for ASIN B07ABC last month", "Ad sales for ASIN B08N5WRWNW", "How many orders did B06XYZ get this week?"
   - **NOTE**: Do NOT use analytics_reporting for simple payload data questions (marketplaces count, wallet balance, login location)
   - **NOTE**: ASIN performance analysis, listing quality, title/description/keyword analysis, product features → these still go to insights_kb. Only transactional/numerical ASIN data comes to analytics_reporting.
   
3. **insights_kb**: (A) Category insights & strategies, OR (B) ASIN performance analysis & best practices, OR (C) ASIN listing content, OR (D) ASIN product features/details
   - (A) **Category Insights**: Insights for a category, top strategies for a category, category-level best practices
   - Examples: "Give me insights for my category", "What are the top strategies for the wireless earbuds category?", "Show me insights for kitchen appliances category"
   - (B) **ASIN Performance Analysis**: "How is my ASIN performing?", "Analyze ASIN X and give me best practices" — use insights_kb (NOT analytics_reporting)
   - Examples: "How is my ASIN B08XYZ123 performing?", "Analyze ASIN B09ABC456 and give me best practices", "ASIN performance for B07ABC"
   - (C) **ASIN content / listing insights**: Title analysis, description analysis, bullet points, keywords, listing quality for an ASIN
   - Examples: "Title analysis for ASIN B09T3ML6QZ", "Description analysis of B08XYZ", "Listing quality for this product"
   - (D) **ASIN product features/details**: Questions about what features/details are in an ASIN's listing (e.g. "What are the key features of B006JSOZLC?", "What does ASIN B08XYZ include?", "Tell me about product B09ABC")
   - Examples: "What are the key features of B006JSOZLC?", "What are the specifications of ASIN B08XYZ?", "Tell me about the features of B09ABC", "What does B07ABC include?"
   
4. **out_of_scope**: Non-e-commerce queries (e.g. weather, recipes, news, general knowledge, off-topic content). NOT for "Who is this?" / "Who are you?" — those are product_detail. NOT for simple greetings or social openers like "Hi", "Hello", "Hey", "Thanks", "Bye" — those are product_detail (friendly connection; route there so the assistant can respond warmly).

**ROUTING RULE (analytics vs insights):**
- **analytics_reporting**: (1) Aggregate numbers — total sales, best-selling products (ranked list), inventory levels, inventory value, quarter comparisons; (2) **ALL Amazon Ads queries** — ad sales, ad spend, ACOS, ROAS, campaign performance, top/best performing campaigns, impressions, clicks; (3) **ASIN-level transactional/numerical data** — sales, revenue, refunds, cancellations, returns, orders for a specific ASIN. "Show me the data."
- **insights_kb**: (1) Category insights & strategies; (2) **ASIN performance analysis** ("How is my ASIN X performing?", "Analyze ASIN X", "Best practices for ASIN X"); (3) ASIN listing content (title, description, keywords); (4) **ASIN product features/details** ("What are the key features of B006JSOZLC?", "What does ASIN X include?", "Tell me about product B08XYZ"). Textual / strategic / qualitative insights.
- **CRITICAL**: Numerical insights (metrics, data, reports) → **analytics_reporting**. Textual insights (analysis, best practices, features, listing quality) → **insights_kb**.
- **CRITICAL**: Route ALL Amazon Ads queries (campaigns, ad spend, ACOS, ROAS, "top performing campaigns", etc.) to **analytics_reporting**.
- **CRITICAL**: "Analyze ASIN" / "How is my ASIN performing?" / "Best practices for ASIN" / "What are the features of ASIN X" / "What does ASIN X include" / listing quality / title/keyword analysis → **insights_kb**. Only transactional/numerical ASIN data (sales, orders, refunds, ad sales for a specific ASIN) → **analytics_reporting**.

**ENRICHMENT RULES:**
1. **PRESERVE ALL PARTS**: If the user's message has multiple parts (e.g. a problem + a request, or "revenue was bad" + "which agent can help?"), the enriched query MUST include every part. Do NOT collapse into a single simplified question.
   → Example: "I did not get the expected revenue last month. Any agent you have to improve it?" → "My revenue last month was below expectations. Which agent(s) do you have or suggest to improve it?" (keeps both: revenue problem AND ask for agents)

2. If query is a FOLLOW-UP (uses "it", "that", "how many", "what about", etc.):
   → Make it complete using conversation history
   → Example: "How many?" after discussing returns → "How many orders were returned?"

3. If query is about **USER'S DATA (sales/orders/metrics)** (typically analytics_reporting) OR about **insights_kb** (category insights, ASIN performance, or ASIN listing content) AND user has MULTIPLE marketplaces:
   → Include ALL marketplaces in the enriched query so the answer considers every registered marketplace
   → Example (analytics): "What is my sales?" with [Amazon, ONDC, Flipkart] → "What is my sales across Amazon, ONDC and Flipkart?"
   → Example (insights_kb category): "Get me insights of running shoes" with [Amazon, Flipkart] → "Get me insights for the running shoes category across Amazon and Flipkart."
   → Example (insights_kb ASIN): "How is my ASIN B08XYZ123 performing?" with [Amazon, Flipkart] → "How is my ASIN B08XYZ123 performing across Amazon and Flipkart."

4. If query ALREADY mentions a specific marketplace:
   → Keep it as-is, don't add other marketplaces (for both analytics_reporting and insights_kb)
   → Example (analytics): "What is my Amazon sales?" → "What is my Amazon sales?"
   → Example (insights_kb): "How is my ASIN B08XYZ123 performing on Amazon?" → "How is my ASIN B08XYZ123 performing on Amazon?"

5. If query is ALREADY complete and self-contained (and has no multiple parts to preserve):
   → Keep it unchanged

**RESPOND WITH JSON ONLY (no explanation):**
{{"category": "<intent_category>", "enriched_query": "complete self-contained query that preserves all parts of the user message", "asins": ["ASIN1", "ASIN2"], "category_name": null or "exact category phrase from user", "query_category_id": null or "numeric category id string", "marketplace_from_query": null or "marketplace api string", "user_needs": null or "analysis type phrase from user", "requires_long_term_memory": true or false}}
- Use "asins": [] when the query has no ASINs. Extract every ASIN mentioned in the user query into "asins".
- Use "category_name": null when the user did not explicitly mention a product/topic category. Use "category_name": "user's exact phrase" only when they clearly stated one (e.g. "insights for wireless earbuds" → "wireless earbuds"). Never invent or assume a category name.
- Use "query_category_id": null when the user did not mention a numeric category ID. Use "query_category_id": "1983610031" (as string) only when they explicitly mention a category id (e.g. "Get me insights for category id: 1983610031").
- Use "marketplace_from_query": null when the user did NOT explicitly mention a specific marketplace. When the user DOES mention a marketplace (e.g. "on Amazon.com", "for amazon.in", "on Amazon", "Amazon.com"), set this to the API format: "amazon.com", "amazon.in", "amazon.co.uk", "amazon.ca", "amazon.com.mx", "amazon.ae". Use lowercase. Examples: "Amazon.com" → "amazon.com", "Amazon.in" → "amazon.in".
- Use "user_needs": null when the user did not explicitly mention specific analysis types. Use "user_needs": "user's exact phrase" only when they clearly stated what they want analyzed (e.g. "title and description analysis" → "title and description analysis", "keyword analysis" → "keyword analysis"). Never invent or assume user needs.
- Use "requires_long_term_memory": true when the query cannot be answered without prior conversation context (references like "my top selling ASIN", "that product", "it"). Use "requires_long_term_memory": false when the user explicitly provides all needed identifiers (ASINs, category name, category ID) in the current query."""

        
        # Format messages for Gemini
        formatted_messages = [{
            "role": "user",
            "content": classification_prompt
        }]

        # Invoke Gemini for classification + enrichment
        response_text, input_tokens, output_tokens = invoke_gemini_with_tokens(
            formatted_messages=formatted_messages,
            system_prompt="",
            max_tokens=2000,  # Room for enriched query and asins array
            temperature=0.1,  # Low temperature for consistent results
        )

        logger.debug(f"LLM classification response: {response_text}")
        logger.info(f"Classification tokens - Input: {input_tokens}, Output: {output_tokens}")

        # Parse category, enriched query, asins, category_name, query_category_id, marketplace_from_query, user_needs, and requires_long_term_memory from JSON response
        category_id, enriched_query, asins, category_name, query_category_id, marketplace_from_query, user_needs, requires_long_term_memory = self._parse_classification_response(response_text, user_message)

        # Fallback: if LLM did not return marketplace_from_query, try to extract from user message
        if not marketplace_from_query and user_message:
            marketplace_from_query = self._extract_marketplace_from_text(user_message)

        # ASIN extraction: rely solely on LLM. No fallback regex (avoids false positives like "PERFORMING").

        # Do not treat query_category_id as an ASIN: exclude it from asins so insights_kb uses INSIGHTS_API_URL
        if query_category_id and asins:
            cat_id_str = str(query_category_id).strip()
            before = len(asins)
            asins = [a for a in asins if str(a).strip() != cat_id_str]
            if len(asins) < before:
                logger.info(f"Excluded category ID {cat_id_str} from ASINs (will use insights API for category ID)")

        # Validate category
        if not category_id or category_id not in self.available_categories:
            # If we have ASINs and the query seems to be about ASIN content/features,
            # route to insights_kb instead of product_detail
            if asins:
                # Check if query is about ASIN content/features (not platform features)
                # Use more specific patterns to avoid false positives
                query_lower = user_message.lower()
                asin_content_patterns = [
                    r"what.*features?", r"what.*specs?", r"what.*specifications?",
                    r"what.*details?", r"what.*includes?", r"what.*contains?",
                    r"tell.*about", r"show.*features?", r"describe",
                    r"features?.*of", r"specs?.*of", r"details?.*of",
                    r"analysis", r"analyze", r"performance", r"performing",
                    r"title", r"description", r"bullet", r"keywords?", r"listing"
                ]
                if any(re.search(pattern, query_lower) for pattern in asin_content_patterns):
                    logger.info(f"Fallback: Routing to insights_kb based on ASIN content patterns (ASINs: {asins})")
                    category_id = "insights_kb"
                else:
                    # If ASIN is present but no clear content keywords, still route to insights_kb
                    # as queries about ASINs are more likely to be about product details than platform features
                    logger.info(f"Fallback: Routing to insights_kb based on ASIN presence (ASINs: {asins})")
                    category_id = "insights_kb"
            else:
                logger.warning(f"Invalid category '{category_id}', falling back to product_detail")
                category_id = "product_detail"

        # Clean up enriched query
        enriched_query = enriched_query.strip().strip('"').strip("'")
        if not enriched_query:
            enriched_query = user_message

        # Log if enrichment happened
        if enriched_query.lower() != user_message.lower():
            logger.info(f"Query enriched: '{user_message}' → '{enriched_query}'")

        if asins:
            logger.info(f"Extracted ASIN(s) from query: {asins}")
        if category_name:
            logger.info(f"Extracted category name from query: {category_name}")
        if query_category_id:
            logger.info(f"Extracted category ID from query: {query_category_id}")
        if marketplace_from_query:
            logger.info(f"Extracted marketplace from query: {marketplace_from_query}")
        if user_needs:
            logger.info(f"Extracted user needs from query: {user_needs}")

        logger.info(f"Intent found: {category_id}, Enriched query length: {len(enriched_query)}, ASINs: {len(asins)}, category_name: {category_name}, query_category_id: {query_category_id}, marketplace_from_query: {marketplace_from_query}, user_needs: {user_needs}, requires_long_term_memory: {requires_long_term_memory}")
        return category_id, enriched_query, asins, category_name, query_category_id, marketplace_from_query, user_needs, requires_long_term_memory

    @observe(name="get_category_for_query")
    async def get_category_for_query(
        self,
        user_message: str,
        intent: Optional[str] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str, List[str], Optional[str], Optional[str], Optional[str], Optional[str], bool]:
        """
        Alias for find_user_intent() for backward compatibility.
        
        Args:
            user_message: User's query message
            intent: Optional pre-detected intent
            chat_history: Previous conversation messages for context
            user_context: User context including marketplaces_registered
            
        Returns:
            Tuple of (category_id, enriched_message, asins, category_name, query_category_id, marketplace_from_query, user_needs, requires_long_term_memory)
        """
        return await self.find_user_intent(user_message, intent, chat_history, user_context)

    @observe(name="process_query")
    async def process_query(
        self,
        user_message: str,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a user query by finding intent, enriching the query, and routing to appropriate category.
        
        Flow:
        1. Build user context from the provided context
        2. Find user intent AND enrich the query using LLM (single call)
        3. Route to the appropriate category handler with the ENRICHED query
        4. Return the category's processed response with enrichment metadata
        
        Args:
            user_message: User's query message
            chat_history: Previous conversation messages
            context: Additional context (language, username, marketplaces_registered, etc.)
            
        Returns:
            Dict with reply, intent, agentId, token counts, category, and enriched_message
        """
        try:
            logger.info(f"Processing user query: {user_message[:100]}...")
            
            # Step 1: Build user context for query enrichment
            user_context = {
                "marketplaces_registered": context.get("marketplaces_registered", []) if context else [],
                "username": context.get("username", "") if context else "",
                "userId": context.get("userId", "") if context else "",
                "walletBalance": context.get("walletBalance") or context.get("wallet_balance") if context else None,
                "wallet_balance": context.get("walletBalance") or context.get("wallet_balance") if context else None,
                "loginLocation": context.get("loginLocation") or context.get("login_location") if context else None,
                "login_location": context.get("loginLocation") or context.get("login_location") if context else None
            }
            logger.debug(f"User context - marketplaces: {user_context.get('marketplaces_registered')}")

            # Set user_id on Langfuse trace for filtering and tracking by user
            user_id = (context or {}).get("userId") or (context or {}).get("user_id")
            if user_id is not None and str(user_id).strip():
                try:
                    get_client().update_current_trace(user_id=str(user_id).strip())
                except Exception:
                    pass  # do not fail the request if Langfuse update fails
            
            # Step 2: Find user intent, enriched query, extracted ASIN(s), category name, query_category_id, marketplace_from_query, user_needs, and requires_long_term_memory (single LLM call!)
            intent = context.get("intent") if context else None
            category_id, enriched_message, asins, category_name, query_category_id, marketplace_from_query, user_needs, requires_long_term_memory = await self.find_user_intent(
                user_message,
                intent,
                chat_history,
                user_context
            )

            # Log enrichment if it happened
            if enriched_message != user_message:
                logger.info(f"Query enriched: '{user_message}' → '{enriched_message}'")

            # When intent requires long-term memory, run LTM DB queries and resolve references
            # (e.g. "my top selling ASIN" → actual ASIN from revenue data); then pass
            # the enriched_query and updated asins to the category.
            # [Disabled for production - re-enable when long_term_memory is ready]
            # if requires_long_term_memory:
            #     user_id = (context or {}).get("userId") or (context or {}).get("user_id")
            #     if user_id is not None and str(user_id).strip():
            #         payload = {"userId": user_id}
            #         try:
            #             enriched_message, asins = await asyncio.to_thread(
            #                 enrich_query_with_ltm_context,
            #                 enriched_message,
            #                 payload,
            #                 asins,
            #             )
            #             logger.info(
            #                 f"Long-term memory enrichment applied: enriched_query length={len(enriched_message)}, asins={asins}"
            #             )
            #         except Exception as e:
            #             logger.warning(f"Long-term memory enrichment failed (continuing with current query): {e}")

            # Validate marketplace access only for non–product_detail intents (e.g. analytics_reporting).
            # For product_detail, allow answers about any marketplace (e.g. "What is ONDC onboarding?").
            if category_id != "product_detail":
                is_mp_valid, mp_error = validate_from_context(user_message, enriched_message, context)
                if not is_mp_valid and mp_error:
                    logger.warning("Marketplace validation failed - returning early")
                    return {
                        **mp_error,
                        "original_message": user_message,
                        "enriched_message": enriched_message,
                        "asins": asins,
                        "category_name": category_name,
                        "query_category_id": query_category_id,
                        "user_needs": user_needs,
                        "requires_long_term_memory": requires_long_term_memory,
                    }

            # ── Step 2b: Finalize enriched query via work_status ──────────
            # The LLM enrichment includes ALL registered marketplaces, but
            # not all of them may be operational for the detected category.
            # work_status filters out unavailable ones and builds a notice.
            # Skip work_status for product_detail: answers can be given for any marketplace.
            if category_id == "product_detail":
                work_status_result = {
                    "enriched_query": enriched_message,
                    "notice": None,
                    "available": [],
                    "unavailable": [],
                    "all_unavailable": False,
                }
            else:
                work_status_result = finalize_enriched_query(
                    category_id=category_id,
                    enriched_query=enriched_message,
                    marketplaces_registered=user_context.get("marketplaces_registered", []),
                )
            enriched_message = work_status_result["enriched_query"]
            route_notice = work_status_result.get("notice")

            if route_notice:
                logger.info(f"Work status notice: {route_notice}")

            # If ALL mentioned marketplaces are unavailable for this category,
            # there is nothing to query — return the notice early.
            # (Skipped for product_detail since we pass through above.)
            if work_status_result.get("all_unavailable"):
                logger.warning(
                    "All mentioned marketplaces unavailable for category '%s' - returning notice only",
                    category_id,
                )
                return {
                    "reply": "",
                    "notice": route_notice,
                    "intent": category_id,
                    "agentId": None,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "category": category_id,
                    "original_message": user_message,
                    "enriched_message": enriched_message,
                    "asins": asins,
                    "category_name": category_name,
                    "query_category_id": query_category_id,
                    "user_needs": user_needs,
                    "requires_long_term_memory": requires_long_term_memory,
                }

            # When ASIN(s) exist and intent is analytics_reporting, validate they belong to the client before proceeding.
            # For other intents (e.g. insights_kb), ASIN validation is skipped.
            if asins and category_id == "analytics_reporting":
                client_id = (context or {}).get("userId") or (context or {}).get("user_id")
                if client_id is not None and str(client_id).strip():
                    try:
                        valid_asins, invalid_asins = await asyncio.to_thread(
                            validate_asins_for_client, client_id, asins
                        )
                        if invalid_asins:
                            logger.warning(f"ASIN(s) not belonging to client {client_id}: {invalid_asins}")
                            # Fetch client's actual ASINs so we can show "these are your listed ASINs"
                            client_asins: List[str] = await asyncio.to_thread(get_client_asins, client_id)
                            if client_asins:
                                reply = (
                                    f"You have given incorrect ASIN(s): {', '.join(invalid_asins)}. "
                                    "Please select one of your ASINs below or enter a correct ASIN."
                                )
                            else:
                                reply = (
                                    f"The following ASIN(s) are not associated with your account: {', '.join(invalid_asins)}. "
                                    "No ASINs were found for your account in the database. "
                                    "Please enter a valid ASIN from your catalog or contact support if you believe this is an error."
                                )
                            return {
                                "reply": reply,
                                "intent": "asin_validation_failed",
                                "agentId": None,
                                "input_tokens": 0,
                                "output_tokens": 0,
                                "category": category_id or "product_detail",
                                "original_message": user_message,
                                "enriched_message": enriched_message,
                                "asins": asins,
                                "invalid_asins": invalid_asins,
                                "client_asins": client_asins,
                                "category_name": category_name,
                                "query_category_id": query_category_id,
                                "user_needs": user_needs,
                                "requires_long_term_memory": requires_long_term_memory,
                            }
                        logger.info(f"All ASIN(s) validated for client {client_id}: {asins}")
                    except Exception as e:
                        logger.warning(f"ASIN validation error (continuing anyway): {e}")

            # Validate category ID
            if not category_id or category_id not in self.categories:
                logger.error(f"Invalid category ID: {category_id}, falling back to product_detail")
                category_id = "product_detail"

            # Step 3: Get the appropriate category handler
            category = self.categories[category_id]
            logger.info(f"Routing query to {category.category_name} category (intent: {category_id})")

            request_context = dict(context) if context else {}
            # Expose extracted ASIN(s), category name, query_category_id, marketplace_from_query, user_needs, and requires_long_term_memory so other components can reuse them
            request_context["asins"] = asins
            request_context["category_name"] = category_name
            request_context["query_category_id"] = query_category_id
            request_context["marketplace_from_query"] = marketplace_from_query
            request_context["user_needs"] = user_needs
            request_context["requires_long_term_memory"] = requires_long_term_memory

            # Step 4: Process the query with the ENRICHED message
            # The enriched message contains full context for better agent responses
            result = await category.process_query(
                user_message=enriched_message,  # Use enriched message!
                chat_history=chat_history,
                context=request_context
            )
            
            # Add metadata to result (including asins, category_name, query_category_id, user_needs, requires_long_term_memory as separate entities for reuse)
            result['category'] = category_id
            result['original_message'] = user_message
            result['enriched_message'] = enriched_message
            result['asins'] = asins
            result['category_name'] = category_name
            result['query_category_id'] = query_category_id
            result['user_needs'] = user_needs
            result['requires_long_term_memory'] = requires_long_term_memory

            # Attach work_status notice (e.g. "Shopclues analytics integration is coming soon…")
            if route_notice:
                existing_notice = result.get('notice')
                if existing_notice:
                    result['notice'] = f"{existing_notice}\n{route_notice}"
                else:
                    result['notice'] = route_notice
            
            logger.info(f"Query processed successfully - category: {category_id}, intent: {result.get('intent')}")
            return result
            
        except Exception as e:
            logger.error(f"Error in Orchestrator.process_query: {e}", exc_info=True)
            # Fallback to Product Detail category on error
            logger.info("Falling back to Product Detail category due to error")
            try:
                fallback_category = self.categories.get("product_detail")
                if fallback_category:
                    result = await fallback_category.process_query(
                        user_message=user_message,
                        chat_history=chat_history,
                        context=context
                    )
                    result['original_message'] = user_message
                    result['enriched_message'] = user_message
                    result['asins'] = []
                    result['category_name'] = None
                    result['query_category_id'] = None
                    result['user_needs'] = None
                    result['requires_long_term_memory'] = False
                    return result
            except Exception as fallback_error:
                logger.error(f"Fallback category also failed: {fallback_error}", exc_info=True)
            
            # Last resort: return error response
            return {
                'reply': f"I encountered an error processing your request. Please try again or contact support.",
                'intent': 'general_query',
                'agentId': None,
                'input_tokens': 0,
                'output_tokens': 0,
                'category': 'product_detail',
                'original_message': user_message,
                'enriched_message': user_message,
                'asins': [],
                'category_name': None,
                'query_category_id': None,
                'user_needs': None,
                'requires_long_term_memory': False,
                'error': str(e)
            }
    
    def get_available_categories(self) -> List[Dict[str, str]]:
        """
        Get list of all available categories.
        
        Returns:
            List of category info dicts
        """
        return [
            category.get_category_info()
            for category in self.categories.values()
        ]


# Singleton instance
_orchestrator: Optional[Orchestrator] = None


@observe(name="get_orchestrator")
def get_orchestrator() -> Orchestrator:
    """
    Get or create the Orchestrator singleton instance.
    
    Returns:
        Orchestrator instance
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator

