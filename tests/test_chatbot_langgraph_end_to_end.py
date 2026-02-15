#!/usr/bin/env python3
"""
End-to-end test script for the LangGraph-based chatbot workflow.

This script:
- Calls the FastAPI `/api/chat/message` endpoint directly (no external server needed)
- Sends a few representative queries that should route to different engines:
  * product_detail
  * analytics_reporting  (with agent-to-agent suggestion path)
- Prints the structured response so you can manually verify behaviour.

Run:
    python3 tests/test_chatbot_langgraph_end_to_end.py
"""

import json
import os
import sys
from typing import Any, Dict

from fastapi.testclient import TestClient

# Add project root to path for imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.api.routes import app  # noqa: E402


client = TestClient(app)


def _make_base_payload(message: str) -> Dict[str, Any]:
    """
    Build a minimal-but-realistic SendMessageRequest payload.

    You can tweak values here (userId, marketplaces, wallet_balance, etc.)
    to test different flows.
    """
    return {
        "message": message,
        "conversationId": "new",  # let backend create a new conversation
        "messageType": "text",
        "language": "English",
        "context": {
            "userId": "test-user-123",
            "username": "Test User",
            "marketplaces_registered": ["Amazon.in"],
            "wallet_balance": 500.0,
            "previousIntent": None,
            "loginLocation": "India",
            "clientInfo": {
                "device": "desktop",
                "appVersion": "1.0.0",
                "timezone": "Asia/Kolkata",
                "platform": "web",
                "userAgent": "pytest-client",
                "country": "IN",
            },
            "metadata": {},
        },
    }


def run_single_test(name: str, message: str) -> None:
    """Send a single message and pretty-print the structured response."""
    print("\n" + "=" * 80)
    print(f"TEST: {name}")
    print("=" * 80)
    print(f"User message: {message!r}\n")

    payload = _make_base_payload(message)
    response = client.post("/api/chat/message", json=payload)

    print(f"HTTP status: {response.status_code}")
    if not response.ok:
        print("Response text:")
        print(response.text)
        return

    body = response.json()
    print("\nStructured response JSON:")
    print(json.dumps(body, indent=2, ensure_ascii=False))

    # Short summary
    data = (body or {}).get("data") or {}
    intent = data.get("intent")
    reply = data.get("reply") or ""
    notice = data.get("notice")

    print("\nSummary:")
    print(f"- intent: {intent}")
    print(f"- reply preview: {reply[:200]!r}")
    if notice:
        print(f"- notice: {notice!r}")


def main() -> None:
    """
    Run a small suite of manual E2E tests.

    NOTE: These tests hit the real LLM / analytics stack, so they assume:
    - GEMINI/GOOGLE_API_KEY is configured
    - Analytics endpoint is reachable
    - MongoDB / Postgres config is valid
    """
    # 1) Product-detail style query (features / agents / pricing)
    run_single_test(
        "product_detail: agent suggestion",
        "I want to improve my Amazon listings. Which AI agents do you have for this?",
    )

    # 2) Analytics-reporting query (should go through analytics engine
    #    and then product_suggestion agent-to-agent hop)
    run_single_test(
        "analytics_reporting: sales analytics + suggestions",
        "What were my total sales last month across all my marketplaces?",
    )

    # 3) Simple greeting (should still be handled as product_detail)
    run_single_test(
        "product_detail: greeting",
        "Hi, what can you do for my e-commerce business?",
    )


if __name__ == "__main__":
    main()

