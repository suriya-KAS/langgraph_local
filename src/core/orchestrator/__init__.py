"""
Orchestrator module for query intent classification and routing.

NOTE: The main orchestration has been migrated to the LangGraph workflow
in ``src/graph/``.  The Orchestrator class is still used internally by
the LangGraph nodes for its ``find_user_intent()`` method (LLM-based
classification + query enrichment).

This module provides the Orchestrator class that:
1. Classifies user queries into categories (product_detail, analytics_reporting, etc.)
2. Routes queries to the appropriate category handler (legacy — now handled by LangGraph)
"""
from src.core.orchestrator.user_intent import Orchestrator, get_orchestrator

__all__ = ['Orchestrator', 'get_orchestrator']

