"""
Insights KB Category

Handles queries about product categories and category insights:
- Exploring a product category (Electronics, Laptops, Fashion, etc.)
- Category-level insights and discovery

- When user provides a category ID: calls insights API only; response is shown in the reply.
- When user does not provide a category ID: uses category-mapper API only and displays
  category paths as clickable buttons.

- When insights API returns data: only text_insights is parsed and sent to Gemini 2.0 Flash;
  the LLM answer (based on user query and insights context) is shown in the frontend.
"""
from typing import Dict, Optional, List, Any, Tuple
import asyncio
import json
import httpx
from src.categories.base_category import BaseCategory
from src.core.asin_validator import get_category_ids_by_asin, get_marketplace_and_category_by_asin
from src.core.backend import invoke_gemini_with_tokens
from utils.logger_config import get_logger

logger = get_logger(__name__)

# Display name (e.g. "Amazon.in") -> API format (e.g. "amazon.in")
MARKETPLACE_TO_API_FORMAT: Dict[str, str] = {
    "amazon.in": "amazon.in",
    "amazon.com": "amazon.com",
    "amazon.co.uk": "amazon.co.uk",
    "amazon.ca": "amazon.ca",
    "amazon.com.mx": "amazon.com.mx",
    "amazon.ae": "amazon.ae",
    "vendorcentral.amazon.com": "vendorcentral.amazon.com",
    "www.vendorcentral.in": "www.vendorcentral.in",
    "flipkart.com": "flipkart.com",
    "flipkart": "flipkart.com",
    "walmart.com": "walmart.com",
    "walmart": "walmart.com",
    "shopify.com": "shopify.com",
    "shopify.com/in": "shopify.com/in",
    "shopify.in": "shopify.in",
    "shopify": "shopify.com",
    "shopclues": "shopclues",
    "ondc": "ondc",
    "ebay.com": "ebay.com",
    "ebay": "ebay.com",
    "meesho": "meesho",
}


def _normalize_marketplace_to_api(mp: str) -> str:
    """Convert display marketplace name to API format (e.g. Amazon.in -> amazon.in)."""
    key = mp.strip().lower().replace(" ", "")
    return MARKETPLACE_TO_API_FORMAT.get(key, key)


def _marketplace_id_to_api_format(marketplace_id: int) -> Optional[str]:
    """
    Convert marketplace_id (integer) to API format marketplace string.
    
    Args:
        marketplace_id: Integer marketplace ID from database
        
    Returns:
        Marketplace string in API format (e.g. "amazon.com", "amazon.in") or None if not found
    """
    # Mapping from marketplace_id to API format
    MARKETPLACE_ID_TO_API = {
        1: "amazon.in",
        2: "amazon.com",
        3: "amazon.co.uk",
        8: "amazon.ca",
        9: "amazon.com.mx",
        10: "amazon.ae",
        6: "flipkart.com",
        7: "walmart.com",
        11: "shopify.com",
        12: "ondc",
        13: "shopclues",
        14: "shopify.com/in",
        15: "www.vendorcentral.in",
        16: "vendorcentral.amazon.com",
        17: "ebay.com",
    }
    return MARKETPLACE_ID_TO_API.get(marketplace_id)


# System prompt for Gemini when answering from insights API text_insights
INSIGHTS_LLM_SYSTEM_PROMPT = """You are an expert at explaining product listing and category insights to sellers.

You will receive:
1) The user's question or request about a category or listing.
2) Raw insights data (text_insights) from our insights API—this may be a JSON-like or dictionary-style structure containing red flags, recommendations, distribution info, and other analysis.

Your task: Answer the user's question clearly and concisely using ONLY the provided insights context. Use plain language, short paragraphs or bullets where helpful. Do not invent data; if the insights do not contain information relevant to the question, say so. Do not output raw JSON or code—only natural language that is ready to show in a chat frontend."""

# System prompt for Gemini when answering from product details API (single product)
PRODUCT_DETAILS_LLM_SYSTEM_PROMPT = """You are an expert at explaining product information to sellers and customers.

You will receive:
1) The user's question or request about a product (identified by ASIN).
2) Product details data from our product-details API—this contains product name, description, specifications, pricing, ratings, images, and other product information.

Your task: Answer the user's question clearly and concisely using ONLY the provided product details. Focus on the specific information requested (e.g., key features, specifications, pricing, etc.). Use plain language, short paragraphs or bullets where helpful. Do not invent data; if the product details do not contain information relevant to the question, say so. Do not output raw JSON or code—only natural language that is ready to show in a chat frontend."""

# System prompt for Gemini when answering from product details API (multiple products)
PRODUCT_DETAILS_MULTI_LLM_SYSTEM_PROMPT = """You are an expert at explaining product information to sellers and customers.

You will receive:
1) The user's question or request about one or more products (identified by ASIN).
2) Product details data for EACH requested ASIN from our product-details API. Each product's data includes product name, description, specifications, pricing, ratings, images, and other product information. Some products may have "No product details available" if the API could not fetch data for that ASIN.

Your task: Answer the user's question clearly and concisely using ONLY the provided product details. For multiple products, provide insights for EACH product requested—do not omit any ASIN. If data is missing for an ASIN, explicitly state that information is not available for that ASIN. Use plain language, short paragraphs or bullets where helpful. Do not invent data; if the product details do not contain information relevant to the question, say so. Do not output raw JSON or code—only natural language that is ready to show in a chat frontend."""


class InsightsKbCategory(BaseCategory):
    """
    Insights KB Category.

    Handles queries where the user asks about or explores a product category.
    - When user provides a category ID: calls insights API only (no category-mapper).
    - When user does not provide a category ID: calls category-mapper API only.
    """

    CATEGORY_MAPPER_URL = "https://ai-dev.mysellercentral.com/common-api-endpoints/api/v1/category-mapper"
    INSIGHTS_API_URL = "https://ai-dev.mysellercentral.com/common-api-endpoints/api/v1/insights"
    PRODUCT_DETAILS_API_URL = "https://ai-dev.mysellercentral.com/common-api-endpoints/api/v1/product-details"

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

    async def _fetch_mapped_taxonomy(
        self,
        category_name: str,
        marketplaces: List[str],
        category_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Call the category-mapper API and return the parsed response.

        Args:
            category_name: Product category as string (e.g. "Buses")
            marketplaces: List of marketplace identifiers (e.g. ["amazon.in"])
            category_id: Optional numeric category ID from user query (e.g. "1983610031")

        Returns:
            Parsed JSON response or None on error
        """
        payload: Dict[str, Any] = {
            "category_name": str(category_name).strip(),
            "marketplaces": [m for m in marketplaces if m],
        }
        if category_id and str(category_id).strip():
            payload["category_id"] = str(category_id).strip()
        if not payload["category_name"] and not payload.get("category_id"):
            logger.warning("Neither category name nor category_id provided, skipping API call")
            return None
        if not payload["marketplaces"]:
            logger.warning("No marketplaces provided, skipping API call")
            return None

        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    self.CATEGORY_MAPPER_URL,
                    json=payload,
                    headers={
                        "accept": "application/json",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()
                logger.info(
                    f"Category-mapper API success for '{category_name}' "
                    f"on {marketplaces}: {len(data.get('mapped_taxonomy', {}))} marketplaces"
                )
                return data
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Category-mapper API HTTP error: {e.response.status_code} - {e.response.text}"
            )
            return None
        except Exception as e:
            logger.error(f"Category-mapper API error: {e}", exc_info=True)
            return None

    async def _fetch_product_details(
        self,
        product_id: str,
        marketplace: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Call the product-details API with product_id (ASIN) and marketplace.

        Args:
            product_id: Product ID/ASIN as string (e.g. "B006JSOZLC").
            marketplace: Marketplace as string (e.g. "amazon.com").

        Returns:
            Parsed JSON response or None on error.
        """
        payload: Dict[str, Any] = {
            "product_id": str(product_id).strip(),
            "marketplace": str(marketplace).strip(),
        }
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    self.PRODUCT_DETAILS_API_URL,
                    json=payload,
                    headers={
                        "accept": "application/json",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()
                logger.info(f"Product-details API success for product_id={product_id}, marketplace={marketplace}")
                return data
        except httpx.HTTPStatusError as e:
            logger.error(f"Product-details API HTTP error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Product-details API error: {e}", exc_info=True)
            return None

    async def _fetch_insights(
        self,
        category_id: str,
        marketplace: str,
        content_types: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Call the insights API with category_id and return the response.

        Args:
            category_id: Category ID as string (e.g. "378531011").
            marketplace: Marketplace as string (e.g. "amazon.com").
            content_types: List of content types (e.g. ["text"]). Defaults to ["text"].

        Returns:
            Parsed JSON response or None on error.
        """
        payload: Dict[str, Any] = {
            "category_id": str(category_id).strip(),
            "marketplace": str(marketplace).strip(),
            "content_types": list(content_types) if content_types else ["text"],
        }
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    self.INSIGHTS_API_URL,
                    json=payload,
                    headers={
                        "accept": "application/json",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()
                logger.info(f"Insights API success for category_id={category_id}, marketplace={marketplace}")
                return data
        except httpx.HTTPStatusError as e:
            logger.error(f"Insights API HTTP error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Insights API error: {e}", exc_info=True)
            return None

    @staticmethod
    def _extract_text_insights(api_response: Dict[str, Any]) -> Optional[str]:
        """
        Extract only the text_insights.insights value from the insights API response.
        Returns the raw string (e.g. JSON-like or dict repr) or None if missing/empty.
        """
        if not api_response or not isinstance(api_response, dict):
            return None
        text_insights = api_response.get("text_insights")
        if not text_insights or not isinstance(text_insights, dict):
            return None
        insights = text_insights.get("insights")
        if insights is None:
            return None
        if isinstance(insights, str) and insights.strip():
            return insights.strip()
        if isinstance(insights, (dict, list)):
            try:
                return json.dumps(insights, indent=2, ensure_ascii=False)
            except Exception:
                return str(insights)
        return str(insights) if insights else None

    async def _generate_insights_reply_via_llm(
        self, user_query: str, text_insights_context: str
    ) -> tuple:
        """
        Call Gemini 2.0 Flash with user query and text_insights context; return (reply_text, input_tokens, output_tokens).
        Runs the sync invoke_gemini_with_tokens in an executor to avoid blocking the event loop.
        """
        user_content = (
            f"User question or request:\n{user_query}\n\n"
            f"Insights data (text_insights) to use as context:\n{text_insights_context}"
        )
        formatted_messages = [{"role": "user", "content": user_content}]

        def _invoke_sync():
            return invoke_gemini_with_tokens(
                formatted_messages=formatted_messages,
                system_prompt=INSIGHTS_LLM_SYSTEM_PROMPT,
                max_tokens=2048,
                temperature=0.2,
            )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()
        response_text, input_tokens, output_tokens = await loop.run_in_executor(
            None, _invoke_sync
        )
        return (response_text or "").strip(), input_tokens or 0, output_tokens or 0

    async def _generate_product_details_reply_via_llm(
        self, user_query: str, product_details: Dict[str, Any]
    ) -> tuple:
        """
        Call Gemini 2.0 Flash with user query and product details context; return (reply_text, input_tokens, output_tokens).
        Runs the sync invoke_gemini_with_tokens in an executor to avoid blocking the event loop.
        
        Args:
            user_query: User's original question/request
            product_details: Product details API response dictionary
            
        Returns:
            Tuple of (reply_text, input_tokens, output_tokens)
        """
        # Convert product_details dict to JSON string for LLM context
        try:
            product_details_str = json.dumps(product_details, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to serialize product_details to JSON, using str(): {e}")
            product_details_str = str(product_details)
        
        user_content = (
            f"User question or request:\n{user_query}\n\n"
            f"Product details data to use as context:\n{product_details_str}"
        )
        formatted_messages = [{"role": "user", "content": user_content}]

        def _invoke_sync():
            return invoke_gemini_with_tokens(
                formatted_messages=formatted_messages,
                system_prompt=PRODUCT_DETAILS_LLM_SYSTEM_PROMPT,
                max_tokens=2048,
                temperature=0.2,
            )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()
        response_text, input_tokens, output_tokens = await loop.run_in_executor(
            None, _invoke_sync
        )
        return (response_text or "").strip(), input_tokens or 0, output_tokens or 0

    async def _generate_product_details_multi_reply_via_llm(
        self,
        user_query: str,
        asin_results: List[Tuple[str, str, Optional[Dict[str, Any]]]],
    ) -> tuple:
        """
        Call Gemini 2.0 Flash with user query and multiple product details; return (reply_text, input_tokens, output_tokens).
        Used when user asks for insights for multiple ASINs.
        
        Args:
            user_query: User's original question/request
            asin_results: List of (asin, marketplace, product_details_or_none) tuples
            
        Returns:
            Tuple of (reply_text, input_tokens, output_tokens)
        """
        parts: List[str] = []
        for asin, marketplace, details in asin_results:
            if details and isinstance(details, dict):
                try:
                    details_str = json.dumps(details, indent=2, ensure_ascii=False)
                except Exception:
                    details_str = str(details)
                parts.append(f"Product details for ASIN {asin} ({marketplace}):\n{details_str}")
            else:
                parts.append(f"Product details for ASIN {asin} ({marketplace}): No product details available.")
        
        context_str = "\n\n---\n\n".join(parts)
        user_content = (
            f"User question or request:\n{user_query}\n\n"
            f"Product details data for each ASIN:\n\n{context_str}"
        )
        formatted_messages = [{"role": "user", "content": user_content}]

        def _invoke_sync():
            return invoke_gemini_with_tokens(
                formatted_messages=formatted_messages,
                system_prompt=PRODUCT_DETAILS_MULTI_LLM_SYSTEM_PROMPT,
                max_tokens=4096,
                temperature=0.2,
            )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()
        response_text, input_tokens, output_tokens = await loop.run_in_executor(
            None, _invoke_sync
        )
        return (response_text or "").strip(), input_tokens or 0, output_tokens or 0

    def _format_product_details_reply(self, product_details: Dict[str, Any], user_query: str) -> str:
        """
        Format product details API response into a readable reply string.
        
        Args:
            product_details: Product details API response dictionary
            user_query: Original user query
            
        Returns:
            Formatted reply string with product information
        """
        if not product_details or not isinstance(product_details, dict):
            return "No product details received."
        
        lines = []
        
        # Product name
        product_name = product_details.get("product_name")
        if product_name:
            lines.append(f"**Product Name:** {product_name}")
        
        # ASIN
        asin = product_details.get("asin")
        if asin:
            lines.append(f"**ASIN:** {asin}")
        
        # Price
        price = product_details.get("price")
        price_currency = product_details.get("price_currency", "USD")
        if price is not None:
            currency_symbol = "₹" if price_currency == "INR" else "$"
            lines.append(f"**Price:** {currency_symbol}{price:,.2f} {price_currency}")
            old_price = product_details.get("old_price")
            if old_price and old_price > price:
                lines.append(f"**Original Price:** {currency_symbol}{old_price:,.2f} {price_currency}")
        
        # Rating and reviews
        average_rating = product_details.get("average_rating")
        total_reviews = product_details.get("total_reviews")
        if average_rating is not None:
            rating_text = f"**Rating:** {average_rating}/5"
            if total_reviews:
                rating_text += f" ({total_reviews:,} reviews)"
            lines.append(rating_text)
        
        # Short description
        short_description = product_details.get("short_description")
        if short_description:
            lines.append(f"\n**Description:**\n{short_description}")
        
        # Specifications
        specifications = product_details.get("specifications")
        if specifications and isinstance(specifications, list) and len(specifications) > 0:
            lines.append("\n**Specifications:**")
            for spec in specifications[:10]:  # Limit to first 10 specs
                if isinstance(spec, dict):
                    name = spec.get("name", "")
                    value = spec.get("value", "")
                    if name and value:
                        lines.append(f"- **{name}:** {value}")
        
        # Product overview
        product_overview = product_details.get("product_overview")
        if product_overview and isinstance(product_overview, list) and len(product_overview) > 0:
            lines.append("\n**Product Overview:**")
            for item in product_overview:
                if isinstance(item, dict):
                    name = item.get("name", "")
                    value = item.get("value", "")
                    if name and value:
                        lines.append(f"- **{name}:** {value}")
        
        # Product URL
        product_url = product_details.get("product_url")
        if product_url:
            lines.append(f"\n**Product URL:** {product_url}")
        
        # Availability
        product_availability = product_details.get("product_availability")
        if product_availability:
            lines.append(f"**Availability:** {product_availability}")
        
        return "\n".join(lines) if lines else "Product details retrieved successfully."

    def _format_insights_reply(self, data: Dict[str, Any]) -> str:
        """
        Format the insights API response into a readable reply string.
        Handles common response shapes (content, insights, text, list, or key-value).
        """
        if not data:
            return "No insights data received."
        # Prefer explicit content fields
        for key in ("content", "insights", "text", "message", "result"):
            if key in data and data[key] is not None:
                val = data[key]
                if isinstance(val, str):
                    return val
                if isinstance(val, list):
                    return "\n\n".join(str(item) for item in val)
                return str(val)
        # List at top level -> bullet points
        if isinstance(data, list):
            return "\n".join(f"• {item}" if not isinstance(item, dict) else f"• {item.get('text', item.get('content', str(item)))}" for item in data)
        # Dict: format key-value or nested content
        lines: List[str] = []
        for k, v in data.items():
            if v is None or (isinstance(v, (str, list)) and not v):
                continue
            if isinstance(v, str):
                lines.append(f"**{k}:** {v}")
            elif isinstance(v, list):
                lines.append(f"**{k}:**")
                for item in v:
                    lines.append(f"  • {item if isinstance(item, str) else str(item)}")
            else:
                lines.append(f"**{k}:** {v}")
        return "\n\n".join(lines) if lines else str(data)

    def _extract_category_paths_by_marketplace(
        self, mapped_taxonomy: Dict[str, List[Dict]]
    ) -> Dict[str, List[Dict[str, str]]]:
        """
        Extract category_path entries grouped by marketplace.

        Returns:
            Dict mapping marketplace name to list of {"category_path": str, "category_id": str}
        """
        paths_by_mp: Dict[str, List[Dict[str, str]]] = {}
        for mp, items in mapped_taxonomy.items():
            if not isinstance(items, list):
                continue
            mp_paths: List[Dict[str, str]] = []
            for item in items:
                if isinstance(item, dict) and "category_path" in item:
                    mp_paths.append({
                        "category_path": str(item["category_path"]),
                        "category_id": str(item.get("category_id", "")),
                    })
            if mp_paths:
                paths_by_mp[mp] = mp_paths
        return paths_by_mp

    def _format_marketplace_display_name(self, mp: str) -> str:
        """
        Format marketplace API name to display name.
        e.g., "amazon.in" -> "Amazon.in", "walmart.com" -> "Walmart.com"
        """
        parts = mp.split(".")
        if len(parts) > 1:
            return parts[0].capitalize() + "." + ".".join(parts[1:])
        return mp.capitalize()

    async def process_query(
        self,
        user_message: str,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process an insights KB query (category exploration / insights).

        - Parses category_name (STRING) and marketplaces (LIST) from context
        - Calls category-mapper API
        - Returns reply with category_paths as clickable quickActions

        Args:
            user_message: User's query message
            chat_history: Previous conversation messages
            context: Additional context (category_name, marketplaces_registered from orchestrator)

        Returns:
            Dict with reply, intent, agentId, token counts, category, components (quickActions)
        """
        logger.info(f"InsightsKbCategory received query: {user_message[:100]}...")

        # Parse category_name (STRING) and query_category_id (numeric) from context (from user_intent/orchestrator)
        category_name = context.get("category_name") if context else None
        if category_name is not None and not isinstance(category_name, str):
            category_name = str(category_name)
        category_name = (category_name or "").strip() or None

        query_category_id = context.get("query_category_id") if context else None
        if query_category_id is not None and not isinstance(query_category_id, str):
            query_category_id = str(query_category_id)
        query_category_id = (query_category_id or "").strip() or None

        # Parse user_needs from context (from user_intent/orchestrator)
        user_needs = context.get("user_needs") if context else None
        if user_needs is not None and not isinstance(user_needs, str):
            user_needs = str(user_needs)
        user_needs = (user_needs or "").strip() or None

        # Prefer marketplace explicitly mentioned in the user query (e.g. "on Amazon.com")
        marketplace_from_query = context.get("marketplace_from_query") if context else None
        if marketplace_from_query and isinstance(marketplace_from_query, str) and marketplace_from_query.strip():
            marketplace_from_query = _normalize_marketplace_to_api(marketplace_from_query.strip())
        else:
            marketplace_from_query = None

        # Parse marketplaces (LIST) from context - use marketplaces_registered when user did not specify a marketplace
        raw_marketplaces = context.get("marketplaces_registered", []) if context else []
        if not isinstance(raw_marketplaces, list):
            raw_marketplaces = [raw_marketplaces] if raw_marketplaces else []
        marketplaces = [_normalize_marketplace_to_api(m) for m in raw_marketplaces if m]

        # Check if category was extracted from user_intent (not from ASIN lookup)
        # Store original category_id from user_intent before any ASIN processing
        category_id_from_user_intent = query_category_id

        # When ASIN is found, ONLY use PRODUCT_DETAILS_API_URL (skip CATEGORY_MAPPER_URL and INSIGHTS_API_URL)
        # CATEGORY_MAPPER_URL and INSIGHTS_API_URL should only be used if category is extracted from user_intent
        asins_from_context = context.get("asins", []) if context else []
        # If the only "ASIN" is actually the category ID (e.g. "insights for category id: 1968027031"), use insights API, not product-details
        if query_category_id and asins_from_context:
            cat_id_str = str(query_category_id).strip()
            asins_from_context = [a for a in asins_from_context if str(a).strip() != cat_id_str]
            if not asins_from_context:
                logger.info(f"Treating {cat_id_str} as category ID only (skipping product-details, will use insights API)")

        if isinstance(asins_from_context, list) and asins_from_context:
            asins_to_process = [str(a).strip() for a in asins_from_context if str(a).strip()]
            fallback_marketplace = marketplace_from_query or (marketplaces[0] if marketplaces else "amazon.in")

            # Resolve marketplace for each ASIN in parallel
            async def _resolve_marketplace(asin: str) -> str:
                results = await asyncio.to_thread(get_marketplace_and_category_by_asin, asin)
                if results:
                    _, marketplace_id = results[0]
                    api_format = _marketplace_id_to_api_format(marketplace_id)
                    if api_format:
                        logger.info(f"ASIN {asin}: marketplace={api_format} from DB")
                        return api_format
                logger.info(f"Using fallback marketplace={fallback_marketplace} for ASIN {asin}")
                return fallback_marketplace

            marketplace_tasks = [_resolve_marketplace(asin) for asin in asins_to_process]
            resolved_marketplaces = await asyncio.gather(*marketplace_tasks)

            # Fetch product details for all ASINs in parallel
            fetch_tasks = [
                self._fetch_product_details(product_id=asin, marketplace=mp)
                for asin, mp in zip(asins_to_process, resolved_marketplaces)
            ]
            product_details_responses = await asyncio.gather(*fetch_tasks)

            asin_results: List[Tuple[str, str, Optional[Dict[str, Any]]]] = [
                (asin, mp, resp)
                for asin, mp, resp in zip(asins_to_process, resolved_marketplaces, product_details_responses)
            ]

            success_count = sum(1 for _, _, r in asin_results if r is not None)
            for asin, mp, resp in asin_results:
                if resp:
                    logger.info(f"Product-details API response received for ASIN {asin} with marketplace={mp}")
                else:
                    logger.warning(f"Product-details API call failed for ASIN {asin} with marketplace={mp}")

            if success_count == 0:
                asin_list = ", ".join(asins_to_process)
                reply = (
                    f"I couldn't fetch product details for any of the ASINs ({asin_list}) at the moment. "
                    "Please try again later."
                )
                result = {
                    "reply": reply,
                    "intent": "insights_kb",
                    "agentId": None,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "category": self.category_id,
                }
            else:
                try:
                    reply, input_tokens, output_tokens = await self._generate_product_details_multi_reply_via_llm(
                        user_query=user_message,
                        asin_results=asin_results,
                    )
                    logger.info(
                        f"Product details reply generated via LLM for {len(asins_to_process)} ASIN(s) "
                        f"(input_tokens={input_tokens}, output_tokens={output_tokens})"
                    )
                except Exception as e:
                    logger.warning(
                        f"LLM failed for product details reply, falling back to formatted output: {e}",
                        exc_info=True
                    )
                    parts = []
                    for asin, mp, details in asin_results:
                        if details:
                            parts.append(f"**ASIN {asin} ({mp}):**\n{self._format_product_details_reply(details, user_message)}")
                        else:
                            parts.append(f"**ASIN {asin} ({mp}):** No product details available.")
                    reply = "\n\n---\n\n".join(parts)
                    input_tokens, output_tokens = 0, 0

                result = {
                    "reply": reply,
                    "intent": "insights_kb",
                    "agentId": None,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "category": self.category_id,
                }

            asins = context.get("asins", []) if context else []
            if asins:
                result["asins"] = asins
            return result

        # If ASIN was not found, proceed with category-mapper or insights API
        # Only use CATEGORY_MAPPER_URL and INSIGHTS_API_URL if category is extracted from user_intent (not from ASIN)
        
        # If no category name but we have category ID, use it as the primary identifier; else use query as fallback
        if not category_name and not query_category_id:
            category_name = user_message.strip()[:200]  # Use query as fallback
            logger.info(f"No category_name or query_category_id in context, using query as fallback: {category_name[:50]}...")
        elif query_category_id:
            logger.info(f"Using query_category_id from context: {query_category_id}")

        # When user specified a marketplace in the query, use it; otherwise use marketplaces_registered or default
        if marketplace_from_query:
            marketplaces = [marketplace_from_query]
            logger.info(f"Using marketplace from user query: {marketplace_from_query}")
        elif not marketplaces:
            marketplaces = ["amazon.com"]
            logger.info("No marketplaces in context, defaulting to amazon.com")

        # Branch: category ID present (from user_intent, not from ASIN) → insights API only; no category ID → category-mapper only
        # Only use these APIs if category was extracted from user_intent, not from ASIN lookup
        # Check if category_id came from user_intent (before ASIN processing)
        if category_id_from_user_intent:
            # Only use INSIGHTS_API_URL when user provided a category ID. Do not use CATEGORY_MAPPER_URL.
            marketplace_str = marketplaces[0] if marketplaces else "amazon.com"
            api_response = await self._fetch_insights(
                category_id=query_category_id,
                marketplace=marketplace_str,
                content_types=["text"],
            )
            if not api_response:
                reply = (
                    "I couldn't fetch insights for that category at the moment. "
                    "Please try again later or check the category ID and marketplace."
                )
                input_tokens, output_tokens = 0, 0
            else:
                text_insights_raw = self._extract_text_insights(api_response)
                if text_insights_raw:
                    try:
                        reply, input_tokens, output_tokens = await self._generate_insights_reply_via_llm(
                            user_query=user_message,
                            text_insights_context=text_insights_raw,
                        )
                        logger.info(f"Insights reply generated via LLM (input_tokens={input_tokens}, output_tokens={output_tokens})")
                    except Exception as e:
                        logger.warning(f"LLM failed for insights reply, falling back to formatted API output: {e}", exc_info=True)
                        reply = self._format_insights_reply(api_response)
                        input_tokens, output_tokens = 0, 0
                else:
                    reply = self._format_insights_reply(api_response)
                    input_tokens, output_tokens = 0, 0
            result = {
                "reply": reply,
                "intent": "insights_kb",
                "agentId": None,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "category": self.category_id,
                "insights_source": "insights_api",  # So workflow routes to product_suggestion for agent upsell
            }
            asins = context.get("asins", []) if context else []
            if asins:
                result["asins"] = asins
            return result

        # No category ID: use only CATEGORY_MAPPER_URL (do not call insights API)
        api_response = await self._fetch_mapped_taxonomy(
            category_name=category_name or "General",
            marketplaces=marketplaces,
            category_id=None,  # category-mapper by name only
        )

        # Build reply and components
        if not api_response:
            reply = (
                "I couldn't fetch category mappings at the moment. Try again later. "
                

            )
            components_dict: Optional[Dict[str, Any]] = None
        else:
            mapped_taxonomy = api_response.get("mapped_taxonomy") or {}
            paths_by_marketplace = self._extract_category_paths_by_marketplace(mapped_taxonomy)

            display_name = category_name or "your category"
            
            # Build reply message listing all marketplaces with results
            if paths_by_marketplace:
                mp_names = [self._format_marketplace_display_name(mp) for mp in paths_by_marketplace.keys()]
                if len(mp_names) == 1:
                    reply = (
                        f"Here are the mapped categories for **{display_name}** on {mp_names[0]}. "
                        "Click a category below to explore:"
                    )
                else:
                    mp_list = ", ".join(mp_names[:-1]) + f", and {mp_names[-1]}"
                    reply = (
                        f"Here are the mapped categories for **{display_name}** on {mp_list}. "
                        "Click a category below to explore:"
                    )
                
                # Create marketplace cards with quickActions for each marketplace
                suggested_agents = []
                for mp, paths in paths_by_marketplace.items():
                    mp_display_name = self._format_marketplace_display_name(mp)
                    
                    # Create quickActions for this marketplace (cap at 50 per marketplace)
                    # message: used for backend processing (includes category ID for orchestrator/insights API)
                    # displayMessage: user-facing text stored and shown in chat (no raw category ID)
                    if user_needs:
                        quick_actions = [
                            {
                                "label": p["category_path"],
                                "message": f"Get me {user_needs} for category id: {p['category_id'] or p['category_path']} on {mp_display_name}",
                                "displayMessage": f"Get {user_needs} for {p['category_path']} on {mp_display_name}",
                                "actionType": "message",
                            }
                            for p in paths[:50]
                        ]
                    else:
                        quick_actions = [
                            {
                                "label": p["category_path"],
                                "message": f"Get me insights for category id: {p['category_id'] or p['category_path']} on {mp_display_name}",
                                "displayMessage": f"Get insights for {p['category_path']} on {mp_display_name}",
                                "actionType": "message",
                            }
                            for p in paths[:50]
                        ]
                    
                    # Create a marketplace card (CategoryMapperCard: no agentId, icon, cost, currency, wallet)
                    marketplace_card = {
                        "name": mp_display_name,
                        "features": [f"{len(paths)} category path{'s' if len(paths) != 1 else ''} found"],
                        "action": "message",
                        "marketplace": [mp],
                        "description": f"Category mappings for {display_name} on {mp_display_name}",
                        "quickActions": quick_actions,
                    }
                    suggested_agents.append(marketplace_card)
                
                components_dict = {
                    "categoryMapperCards": suggested_agents,
                }
            else:
                mp_display = ", ".join([self._format_marketplace_display_name(mp) for mp in marketplaces])
                reply = (
                    f"No mapped categories were found for **{display_name}** on {mp_display}. "
                    "Try a different category name or marketplace."
                )
                components_dict = None

        result: Dict[str, Any] = {
            "reply": reply,
            "intent": "insights_kb",
            "agentId": None,
            "input_tokens": 0,
            "output_tokens": 0,
            "category": self.category_id,
        }
        if components_dict:
            result["components"] = components_dict

        asins = context.get("asins", []) if context else []
        if asins:
            result["asins"] = asins

        return result
