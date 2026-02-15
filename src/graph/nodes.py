"""
LangGraph Workflow Node Functions

Each node receives the ChatState and returns a partial state update dict.
Nodes are the building blocks of the workflow graph.

Graph flow (matching the architecture diagram):

    START
      → user_intent_node      (classify intent, enrich query, validate)
      → route_after_intent:
          ├─ early_exit             → build_response → END
          ├─ product_detail         → product_detail_engine  → build_response → END
          ├─ recommendation_engine  → recommendation_engine  → build_response → END
          ├─ out_of_scope           → out_of_scope_engine    → build_response → END
          ├─ insights_kb            → insights_kb_engine     → build_response → END
          └─ analytics_reporting    → work_status_node       → route:
                                        ├─ exit     → build_response → END
                                        └─ continue → analytics_engine
                                                       → product_suggestion  (agent-to-agent)
                                                       → build_response → END
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict

from utils.logger_config import get_logger
from src.graph.state import ChatState

logger = get_logger(__name__)


# ── Lazy-initialized singletons ──────────────────────────────────────────

_orchestrator = None
_categories = None


def _get_orchestrator():
    """
    Get or create the Orchestrator singleton.

    Used **only** for its ``find_user_intent`` method (LLM classification +
    query enrichment).  The Orchestrator also initialises all category
    handler instances, which we reuse via ``_get_categories()``.
    """
    global _orchestrator
    if _orchestrator is None:
        from src.core.orchestrator.user_intent import Orchestrator
        _orchestrator = Orchestrator()
        logger.info("LangGraph: Orchestrator singleton initialised for intent classification")
    return _orchestrator


def _get_categories():
    """Return category handler instances (reuses the Orchestrator's instances)."""
    global _categories
    if _categories is None:
        _categories = _get_orchestrator().categories
    return _categories


# ═════════════════════════════════════════════════════════════════════════
# NODE: User Intent
# ═════════════════════════════════════════════════════════════════════════

async def user_intent_node(state: ChatState) -> dict:
    """
    Classify user intent, enrich query, extract ASINs, and validate.

    Steps:
        1. Build user context from the request payload.
        2. Call Orchestrator.find_user_intent (single LLM call for
           classification + enrichment + ASIN extraction).
        3. Validate marketplace access (mp_validator).
        4. If category is analytics_reporting and ASINs are present,
           validate ASINs against the client's catalogue.

    Sets ``early_exit=True`` when any validation fails so that the graph
    can short-circuit to ``build_response``.
    """
    user_message: str = state["user_message"]
    chat_history: list = state.get("chat_history") or []
    context: dict = state.get("context") or {}

    logger.info(f"[user_intent_node] Processing: {user_message[:100]}...")

    # ── Step 1: Build user context ────────────────────────────
    user_context: Dict[str, Any] = {
        "marketplaces_registered": context.get("marketplaces_registered", []),
        "username": context.get("username", ""),
        "userId": context.get("userId", ""),
        "walletBalance": context.get("walletBalance") or context.get("wallet_balance"),
        "wallet_balance": context.get("walletBalance") or context.get("wallet_balance"),
        "loginLocation": context.get("loginLocation") or context.get("login_location"),
        "login_location": context.get("loginLocation") or context.get("login_location"),
    }

    # ── Step 2: Classify intent + enrich query ────────────────
    orchestrator = _get_orchestrator()
    intent_hint = context.get("intent")
    category_id, enriched_query, asins = await orchestrator.find_user_intent(
        user_message, intent_hint, chat_history, user_context,
    )

    if enriched_query != user_message:
        logger.info(f"[user_intent_node] Enriched: '{user_message}' → '{enriched_query}'")

    # ── Step 3: Marketplace validation ────────────────────────
    from src.services.mp_validator import validate_from_context

    is_mp_valid, mp_error = validate_from_context(user_message, enriched_query, context)
    if not is_mp_valid and mp_error:
        logger.warning("[user_intent_node] Marketplace validation failed — early exit")
        return {
            "category": category_id,
            "enriched_query": enriched_query,
            "asins": asins,
            "user_context": user_context,
            "early_exit": True,
            "early_exit_result": {
                **mp_error,
                "original_message": user_message,
                "enriched_message": enriched_query,
                "asins": asins,
            },
        }

    # ── Step 4: ASIN validation (analytics_reporting only) ────
    if asins and category_id == "analytics_reporting":
        from src.core.asin_validator import validate_asins_for_client, get_client_asins

        client_id = context.get("userId") or context.get("user_id")
        if client_id and str(client_id).strip():
            try:
                valid_asins, invalid_asins = await asyncio.to_thread(
                    validate_asins_for_client, client_id, asins,
                )
                if invalid_asins:
                    logger.warning(f"[user_intent_node] Invalid ASINs: {invalid_asins}")
                    client_asins = await asyncio.to_thread(get_client_asins, client_id)
                    if client_asins:
                        reply = (
                            f"You have given incorrect ASIN(s): {', '.join(invalid_asins)}. "
                            "Please select one of your ASINs below or enter a correct ASIN."
                        )
                    else:
                        reply = (
                            f"The following ASIN(s) are not associated with your account: "
                            f"{', '.join(invalid_asins)}. No ASINs were found for your account. "
                            "Please enter a valid ASIN."
                        )
                    return {
                        "category": category_id,
                        "enriched_query": enriched_query,
                        "asins": asins,
                        "user_context": user_context,
                        "early_exit": True,
                        "early_exit_result": {
                            "reply": reply,
                            "intent": "asin_validation_failed",
                            "agentId": None,
                            "input_tokens": 0,
                            "output_tokens": 0,
                            "category": category_id,
                            "original_message": user_message,
                            "enriched_message": enriched_query,
                            "asins": asins,
                            "invalid_asins": invalid_asins,
                            "client_asins": client_asins,
                        },
                    }
                logger.info(f"[user_intent_node] All ASINs validated for client {client_id}")
            except Exception as e:
                logger.warning(f"[user_intent_node] ASIN validation error (continuing): {e}")

    logger.info(
        f"[user_intent_node] Intent: {category_id}, "
        f"Enriched length: {len(enriched_query)}, ASINs: {len(asins)}"
    )
    return {
        "category": category_id,
        "enriched_query": enriched_query,
        "asins": asins,
        "user_context": user_context,
        "early_exit": False,
    }


# ═════════════════════════════════════════════════════════════════════════
# NODE: Work Status Validator
# ═════════════════════════════════════════════════════════════════════════

async def work_status_node(state: ChatState) -> dict:
    """
    Validate marketplace availability for the detected category.

    Called **only** for ``analytics_reporting`` (per the architecture diagram).
    Filters unavailable marketplaces from the enriched query and builds a
    user-facing notice.

    If ALL mentioned marketplaces are unavailable, sets ``early_exit=True``
    so the graph short-circuits to ``build_response``.
    """
    from src.core.orchestrator.work_status import finalize_enriched_query

    category_id: str = state["category"]
    enriched_query: str = state["enriched_query"]
    user_context: dict = state.get("user_context", {})
    marketplaces = user_context.get("marketplaces_registered", [])

    logger.info(f"[work_status_node] Validating for category: {category_id}")

    result = finalize_enriched_query(
        category_id=category_id,
        enriched_query=enriched_query,
        marketplaces_registered=marketplaces,
    )

    notice = result.get("notice") or ""
    all_unavailable = result.get("all_unavailable", False)

    if notice:
        logger.info(f"[work_status_node] Notice: {notice}")

    if all_unavailable:
        logger.warning(
            f"[work_status_node] ALL marketplaces unavailable for '{category_id}' — early exit"
        )
        return {
            "enriched_query": result["enriched_query"],
            "route_notice": notice,
            "work_status_all_unavailable": True,
            "early_exit": True,
            "early_exit_result": {
                "reply": "",
                "notice": notice,
                "intent": category_id,
                "agentId": None,
                "input_tokens": 0,
                "output_tokens": 0,
                "category": category_id,
                "original_message": state["user_message"],
                "enriched_message": result["enriched_query"],
                "asins": state.get("asins", []),
            },
        }

    return {
        "enriched_query": result["enriched_query"],
        "route_notice": notice,
        "work_status_all_unavailable": False,
    }


# ═════════════════════════════════════════════════════════════════════════
# ENGINE NODES — one per category
# ═════════════════════════════════════════════════════════════════════════

async def product_detail_engine_node(state: ChatState) -> dict:
    """Route query through the **Product Detail** category handler."""
    categories = _get_categories()
    engine = categories["product_detail"]

    context = dict(state.get("context") or {})
    context["asins"] = state.get("asins", [])

    logger.info("[product_detail_engine] Processing query")
    result = await engine.process_query(
        user_message=state["enriched_query"],
        chat_history=state.get("chat_history"),
        context=context,
    )
    return {"engine_result": result}


async def analytics_engine_node(state: ChatState) -> dict:
    """Route query through the **Analytics & Reporting** category handler."""
    categories = _get_categories()
    engine = categories["analytics_reporting"]

    context = dict(state.get("context") or {})
    context["asins"] = state.get("asins", [])

    logger.info("[analytics_engine] Processing query")
    result = await engine.process_query(
        user_message=state["enriched_query"],
        chat_history=state.get("chat_history"),
        context=context,
    )
    return {"engine_result": result}


async def recommendation_engine_node(state: ChatState) -> dict:
    """Route query through the **Recommendation Engine** category handler."""
    categories = _get_categories()
    engine = categories["recommendation_engine"]

    context = dict(state.get("context") or {})
    context["asins"] = state.get("asins", [])

    logger.info("[recommendation_engine] Processing query")
    result = await engine.process_query(
        user_message=state["enriched_query"],
        chat_history=state.get("chat_history"),
        context=context,
    )
    return {"engine_result": result}


async def out_of_scope_engine_node(state: ChatState) -> dict:
    """Route query through the **Out of Scope** category handler."""
    categories = _get_categories()
    engine = categories["out_of_scope"]

    context = dict(state.get("context") or {})
    context["asins"] = state.get("asins", [])

    logger.info("[out_of_scope_engine] Processing query")
    result = await engine.process_query(
        user_message=state["enriched_query"],
        chat_history=state.get("chat_history"),
        context=context,
    )
    return {"engine_result": result}


async def insights_kb_engine_node(state: ChatState) -> dict:
    """Route query through the **Insights KB** category handler."""
    categories = _get_categories()
    engine = categories["insights_kb"]

    context = dict(state.get("context") or {})
    context["asins"] = state.get("asins", [])

    logger.info("[insights_kb_engine] Processing query")
    result = await engine.process_query(
        user_message=state["enriched_query"],
        chat_history=state.get("chat_history"),
        context=context,
    )
    return {"engine_result": result}


# ═════════════════════════════════════════════════════════════════════════
# NODE: Product Suggestion (Agent-to-Agent Communication)
# ═════════════════════════════════════════════════════════════════════════

async def product_suggestion_node(state: ChatState) -> dict:
    """
    Agent-to-agent communication: **analytics_reporting → product_detail**.

    Takes the analytics engine output and passes it to the Product Detail
    engine to generate product-related suggestions (relevant AI agents,
    tools, or features) based on the analytics data.

    This is the "agent 2 agent communication" described in the architecture:
    after analytics_reporting produces its output, that output feeds into
    product_detail to get actionable product suggestions.
    """
    engine_result: dict = state.get("engine_result", {})
    analytics_reply: str = engine_result.get("reply", "")

    if not analytics_reply or not analytics_reply.strip():
        logger.info("[product_suggestion] No analytics reply — skipping suggestions")
        return {"product_suggestion": {}}

    categories = _get_categories()
    product_detail = categories["product_detail"]

    # Build a suggestion query that includes analytics context
    suggestion_query = (
        "Based on the following analytics data from the user's account, "
        "suggest relevant MySellerCentral AI agents or tools that could help "
        "improve their metrics or address any issues found in the data. "
        "Keep the suggestion concise (2-4 bullet points max).\n\n"
        f"Analytics Data:\n{analytics_reply[:2000]}"  # Limit to avoid token overflow
    )

    context = dict(state.get("context") or {})

    logger.info("[product_suggestion] Generating product suggestions from analytics output")
    try:
        suggestion_result = await product_detail.process_query(
            user_message=suggestion_query,
            chat_history=None,  # No chat history needed for suggestion
            context=context,
        )
        logger.info("[product_suggestion] Suggestions generated successfully")
        return {"product_suggestion": suggestion_result}
    except Exception as e:
        logger.error(f"[product_suggestion] Error generating suggestions: {e}", exc_info=True)
        return {"product_suggestion": {}}


# ═════════════════════════════════════════════════════════════════════════
# NODE: Build Response
# ═════════════════════════════════════════════════════════════════════════

async def build_response_node(state: ChatState) -> dict:
    """
    Assemble the final API response from engine output and metadata.

    Handles four cases:
        1. **Early exit** — validation error → return pre-built result.
        2. **Normal engine result** — product_detail, recommendation, etc.
        3. **Analytics + product suggestion** — merge analytics data with
           product suggestions (agent-to-agent).
        4. **Work status exit** — all marketplaces unavailable → notice only.
    """
    # ── Case 1 & 4: Early exit ────────────────────────────────
    if state.get("early_exit"):
        logger.info("[build_response] Returning early exit result")
        return {"final_result": state.get("early_exit_result", {})}

    # ── Case 2 & 3: Normal engine result ──────────────────────
    result = dict(state.get("engine_result", {}))

    # Add metadata
    result["category"] = state.get("category", "product_detail")
    result["original_message"] = state["user_message"]
    result["enriched_message"] = state.get("enriched_query", state["user_message"])
    result["asins"] = state.get("asins", [])

    # Attach work_status notice (e.g. "X analytics integration is coming soon…")
    route_notice = state.get("route_notice", "")
    if route_notice:
        existing_notice = result.get("notice")
        result["notice"] = f"{existing_notice}\n{route_notice}" if existing_notice else route_notice

    # ── Case 3: Append product suggestion (agent-to-agent) ────
    product_suggestion: dict = state.get("product_suggestion", {})
    if product_suggestion and product_suggestion.get("reply"):
        suggestion_text = product_suggestion["reply"]

        # Store as separate field for frontend flexibility
        result["product_suggestion"] = {
            "reply": suggestion_text,
            "intent": product_suggestion.get("intent"),
            "agentId": product_suggestion.get("agentId"),
        }

        # Also append to the main reply for immediate display
        main_reply = result.get("reply", "")
        if main_reply:
            result["reply"] = (
                f"{main_reply}\n\n"
                f"---\n\n"
                f"**Suggested Tools & Agents:**\n\n{suggestion_text}"
            )
        logger.info("[build_response] Product suggestions appended to analytics reply")

    logger.info(
        f"[build_response] Final result — category: {result.get('category')}, "
        f"intent: {result.get('intent')}"
    )
    return {"final_result": result}


# ═════════════════════════════════════════════════════════════════════════
# ROUTING FUNCTIONS — used by conditional edges
# ═════════════════════════════════════════════════════════════════════════

def route_after_intent(state: ChatState) -> str:
    """
    Conditional router after ``user_intent_node``.

    Returns the name of the next node based on ``early_exit`` or ``category``.
    """
    if state.get("early_exit"):
        return "early_exit"

    category = state.get("category", "product_detail")

    valid_routes = {
        "product_detail",
        "analytics_reporting",
        "recommendation_engine",
        "out_of_scope",
        "insights_kb",
    }
    if category in valid_routes:
        return category

    logger.warning(
        f"[route_after_intent] Unknown category '{category}', defaulting to product_detail"
    )
    return "product_detail"


def route_after_work_status(state: ChatState) -> str:
    """
    Conditional router after ``work_status_node``.

    Returns ``"exit"`` if all marketplaces are unavailable, ``"continue"``
    otherwise.
    """
    if state.get("early_exit") or state.get("work_status_all_unavailable"):
        return "exit"
    return "continue"
