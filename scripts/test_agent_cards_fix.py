#!/usr/bin/env python3
"""Quick test: generate_components with 'What agents can help me?' + reply that mentions 4 agents."""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.services.intent_extractor import IntentExtractor
from src.core.models import IntentType

REPLY_4_AGENTS = """Hello! To improve your Amazon listings, we have several AI agents:

1. **Smart Listing Agent** (₹30 per use): Upload images or voice notes, get SEO-friendly titles, bullets, descriptions.
2. **Text Grading & Enhancement Agent** (₹20 per use): Analyzes and enhances your listing text, suggests edits.
3. **Image Grading & Enhancement Agent** (₹25 per use): Evaluates image quality, gives improvement tips.
4. **A+ Content Agent** (₹50 per use): Creates media-rich, conversion-optimized brand content.

Each is available on a pay-per-use basis."""

def main():
    ie = IntentExtractor()
    agent_db = ie.get_agent_database(cache_only=True)
    components = ie.generate_components(
        intent=IntentType.AGENT_SUGGESTION,
        llm_response=REPLY_4_AGENTS,
        wallet_balance=1234.0,
        user_message="What agents can help me?",
        agent_id="smart-listing",
        llm_agent_ids=["smart-listing"],
        currency="INR",
        cache_only=True,
        agent_db=agent_db,
    )
    n_primary = 1 if components and components.agentCard else 0
    n_suggested = len(components.suggestedAgents) if components and components.suggestedAgents else 0
    total = n_primary + n_suggested
    print(f"agentCard: {n_primary}, suggestedAgents: {n_suggested}, total cards: {total}")
    assert total == 4, f"Expected 4 cards, got {total}"
    print("OK: 4 agent cards as expected")

if __name__ == "__main__":
    main()
