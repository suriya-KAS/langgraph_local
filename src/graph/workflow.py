"""
LangGraph Workflow Definition

Builds the chatbot workflow as a LangGraph StateGraph.  The compiled graph
replaces the previous custom Orchestrator routing pattern with a proper
graph-based orchestration.

Architecture (matches the architecture diagram):
─────────────────────────────────────────────────

    START
      │
      ▼
    user_intent  ──────────────────────────────┐
      │                                        │
      ▼                                        │ (early_exit)
    route_after_intent ─────────────────────── ▼
      │          │          │         │     build_response ──→ END
      │          │          │         │
      ▼          ▼          ▼         ▼
    product    recom-     out_of   insights_kb
    _detail    mendation  _scope    _engine
    _engine    _engine    _engine      │
      │          │          │     route_after_insights_kb
      │          │          │          ├─ (insights_api) → product_suggestion → build_response
      │          │          │          └─ (category_mapper) → build_response
      └──────────┴──────────┴──────────┴─────────────────────────────────────┐
                       │                              │
                       ▼                              ▼
                  build_response ──────────────────→ END

    analytics_reporting path (if and only if user_intent == analytics_reporting):

    user_intent
      │
      ▼
    work_status ──→ (all_unavailable) ──→ build_response ──→ END
      │
      ▼ (available)
    analytics_engine
      │
      ▼
    product_suggestion  ← agent-to-agent communication
      │
      ▼
    build_response ──→ END
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.graph.nodes import (
    analytics_engine_node,
    build_response_node,
    insights_kb_engine_node,
    out_of_scope_engine_node,
    product_detail_engine_node,
    product_suggestion_node,
    recommendation_engine_node,
    route_after_insights_kb,
    route_after_intent,
    route_after_work_status,
    user_intent_node,
    work_status_node,
)
from src.graph.state import ChatState
from utils.logger_config import get_logger

logger = get_logger(__name__)


def build_workflow():
    """
    Build and compile the LangGraph chatbot workflow.

    Returns:
        A compiled ``StateGraph`` ready for ``ainvoke()`` / ``invoke()``.
    """
    logger.info("Building LangGraph chatbot workflow…")

    graph = StateGraph(ChatState)

    # ── Add nodes ──────────────────────────────────────────────
    graph.add_node("user_intent", user_intent_node)
    graph.add_node("work_status", work_status_node)
    graph.add_node("product_detail_engine", product_detail_engine_node)
    graph.add_node("analytics_engine", analytics_engine_node)
    graph.add_node("recommendation_engine", recommendation_engine_node)
    graph.add_node("out_of_scope_engine", out_of_scope_engine_node)
    graph.add_node("insights_kb_engine", insights_kb_engine_node)
    graph.add_node("product_suggestion", product_suggestion_node)
    graph.add_node("build_response", build_response_node)

    # ── Entry point ────────────────────────────────────────────
    graph.set_entry_point("user_intent")

    # ── Conditional edges after intent classification ──────────
    graph.add_conditional_edges(
        "user_intent",
        route_after_intent,
        {
            "early_exit": "build_response",
            "product_detail": "product_detail_engine",
            "analytics_reporting": "work_status",
            "recommendation_engine": "recommendation_engine",
            "out_of_scope": "out_of_scope_engine",
            "insights_kb": "insights_kb_engine",
        },
    )

    # ── Conditional edges after work-status validation ─────────
    graph.add_conditional_edges(
        "work_status",
        route_after_work_status,
        {
            "exit": "build_response",
            "continue": "analytics_engine",
        },
    )

    # ── Direct edges: engine → build_response ──────────────────
    graph.add_edge("product_detail_engine", "build_response")
    graph.add_edge("recommendation_engine", "build_response")
    graph.add_edge("out_of_scope_engine", "build_response")

    # ── Analytics flow: engine → product_suggestion → response ─
    graph.add_edge("analytics_engine", "product_suggestion")
    graph.add_edge("product_suggestion", "build_response")

    # ── Insights KB flow: only INSIGHTS_API path → product_suggestion ─
    graph.add_conditional_edges(
        "insights_kb_engine",
        route_after_insights_kb,
        {
            "product_suggestion": "product_suggestion",
            "build_response": "build_response",
        },
    )

    # ── Terminal edge ──────────────────────────────────────────
    graph.add_edge("build_response", END)

    compiled = graph.compile()
    logger.info("LangGraph workflow compiled successfully")
    return compiled


# ── Singleton compiled graph ─────────────────────────────────────────────

_compiled_graph = None


def get_workflow():
    """
    Get or create the compiled workflow singleton.

    Returns:
        Compiled ``StateGraph`` ready for ``await workflow.ainvoke(state)``.
    """
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_workflow()
    return _compiled_graph
