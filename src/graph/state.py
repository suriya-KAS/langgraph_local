"""
LangGraph Workflow State Definition

Defines the ChatState TypedDict that flows through all nodes in the
chatbot workflow graph. Each node reads from and writes to this shared state.

Uses total=False so node functions can return partial state updates —
only the keys they need to set, without providing every field.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class ChatState(TypedDict, total=False):
    """
    Shared state for the LangGraph chatbot workflow.

    Nodes receive this state and return a dict with the keys they want to
    update.  LangGraph merges the returned dict into the existing state.
    """

    # ─── Inputs (set once at invocation) ──────────────────────
    user_message: str                # Original user message from the API
    chat_history: list               # List[Dict[str, Any]] — conversation history
    context: dict                    # Dict[str, Any] — request context (userId, marketplaces, etc.)

    # ─── User Intent Node Output ──────────────────────────────
    category: str                    # Detected category (product_detail, analytics_reporting, …)
    enriched_query: str              # LLM-enriched, self-contained query
    asins: list                      # Extracted ASINs from the query
    user_context: dict               # Built user context for downstream nodes

    # ─── Control Flow ─────────────────────────────────────────
    early_exit: bool                 # True → skip engine, use early_exit_result
    early_exit_result: dict          # Pre-built API result for validation errors

    # ─── Work Status ──────────────────────────────────────────
    route_notice: str                # User-facing notice (e.g. "X coming soon…")
    work_status_all_unavailable: bool  # True when ALL marketplaces are unavailable

    # ─── Engine Output ────────────────────────────────────────
    engine_result: dict              # Output dict from the category engine

    # ─── Agent-to-Agent Communication ─────────────────────────
    product_suggestion: dict         # Product suggestions (analytics → product_detail)

    # ─── Final Output ─────────────────────────────────────────
    final_result: dict               # Assembled final response for the API
