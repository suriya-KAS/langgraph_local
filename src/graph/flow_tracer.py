"""
LangGraph Flow Tracer

Runs the workflow with streaming to capture, for each query, the exact flow:
- Which node runs first, next, etc.
- Input state (snapshot) into each node
- Output (state update) from each node

Use run_workflow_with_flow() instead of workflow.ainvoke() to get (final_state, flow).
Flow is logged and can be returned for debugging or API responses.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List

from utils.logger_config import get_logger

logger = get_logger(__name__)

# Keys we truncate or summarize when logging state (to avoid huge logs)
TRUNCATE_KEYS = ("user_message", "enriched_query", "chat_history", "reply")
MAX_STR_LEN = 200
MAX_LIST_LEN = 5


def _safe_state_snapshot(state: dict) -> dict:
    """
    Build a JSON-serializable, log-friendly snapshot of state.
    Truncates long strings and limits list lengths.
    """
    if not state:
        return {}
    out = {}
    for k, v in state.items():
        if v is None:
            out[k] = None
        elif isinstance(v, str):
            out[k] = v if len(v) <= MAX_STR_LEN else v[:MAX_STR_LEN] + "..."
        elif isinstance(v, list):
            if k == "chat_history" and len(v) > MAX_LIST_LEN:
                out[k] = f"<list len={len(v)}>"
            else:
                out[k] = v[:MAX_LIST_LEN] if len(v) > MAX_LIST_LEN else v
        elif isinstance(v, dict):
            # Nested dicts: truncate nested 'reply' etc.
            try:
                out[k] = _safe_state_snapshot(v)
            except Exception:
                out[k] = "<dict>"
        else:
            out[k] = v
    return out


def _merge_update(state: dict, update: dict) -> dict:
    """Merge node update into state (shallow merge; LangGraph does key-level merge)."""
    result = dict(state)
    for k, v in update.items():
        result[k] = v
    return result


def format_flow_for_log(flow: List[Dict[str, Any]]) -> str:
    """Produce a human-readable summary of the flow for logging."""
    lines = [" LangGraph flow:", " ─────────────────"]
    for i, step in enumerate(flow, 1):
        node = step.get("node", "?")
        lines.append(f" Step {i}: {node}")
        inp = step.get("input_snapshot", {})
        out = step.get("output_update", {})
        if inp:
            lines.append(f"   → Input (relevant keys): {list(inp.keys())}")
        if out:
            lines.append(f"   → Output keys: {list(out.keys())}")
    lines.append(" ─────────────────")
    return "\n".join(lines)


async def run_workflow_with_flow(
    workflow: Any,
    initial_state: dict,
    *,
    log_flow: bool = True,
    include_snapshots_in_flow: bool = True,
) -> tuple[dict, List[Dict[str, Any]]]:
    """
    Run the LangGraph workflow by streaming updates, and build the per-node flow.

    Uses stream_mode="updates" so we get (node_name -> state update) after each node.
    We accumulate state to know the "input" to each node (state before that node ran).

    Args:
        workflow: Compiled LangGraph (from get_workflow()).
        initial_state: Initial ChatState to invoke with.
        log_flow: If True, log a readable flow summary at INFO.
        include_snapshots_in_flow: If True, each step includes input_snapshot and
            output_update (safe, truncated). If False, only node name and keys are kept.

    Returns:
        (final_state, flow):
        - final_state: Full state after the graph run (same as ainvoke would return).
        - flow: List of {"node": str, "input_snapshot": dict, "output_update": dict}
            in execution order. Snapshots are safe for logging/serialization.
    """
    flow: List[Dict[str, Any]] = []
    state = dict(initial_state)

    async for chunk in workflow.astream(initial_state, stream_mode="updates"):
        if not isinstance(chunk, dict):
            continue
        # Chunk format: { "node_name": { ... update ... } }
        for node_name, output_update in chunk.items():
            input_snapshot = _safe_state_snapshot(state) if include_snapshots_in_flow else {}
            step = {
                "node": node_name,
                "input_snapshot": input_snapshot,
                "output_update": copy.deepcopy(output_update) if output_update else {},
            }
            if not include_snapshots_in_flow:
                step["input_keys"] = list(state.keys())
                step["output_keys"] = list(output_update.keys()) if output_update else []
            flow.append(step)
            state = _merge_update(state, output_update or {})

    if log_flow:
        logger.info(format_flow_for_log(flow))

    return state, flow


def get_flow_summary(flow: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Return a compact summary of the flow for API or debugging (node order + keys only).
    """
    steps = []
    for i, s in enumerate(flow, 1):
        out = s.get("output_update") or {}
        keys = list(out.keys()) if out else (s.get("output_keys") or [])
        steps.append({"step": i, "node": s.get("node", "?"), "output_keys": keys})
    return {"steps": steps, "total_steps": len(flow)}
