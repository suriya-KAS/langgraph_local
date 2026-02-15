"""
LangGraph-based Chatbot Workflow
================================

Replaces the custom Orchestrator routing pattern with a proper LangGraph
StateGraph for intent classification, conditional routing, engine dispatch,
and agent-to-agent communication (analytics → product suggestions).

Usage::

    from src.graph import get_workflow

    workflow = get_workflow()
    result_state = await workflow.ainvoke({
        "user_message": "What were my total sales last month?",
        "chat_history": [...],
        "context": {...},
    })
    final_result = result_state["final_result"]
"""

from src.graph.state import ChatState
from src.graph.workflow import build_workflow, get_workflow

__all__ = ["ChatState", "build_workflow", "get_workflow"]
