#!/usr/bin/env python3
"""
Minimal test for ASIN validation and get_client_asins (no LLM/orchestrator).

Usage:
  # Set DATABASE_URL_PRODUCTION in .env, then:
  python3 scripts/test_asin_validation.py <client_id>

Example:
  python3 scripts/test_asin_validation.py 1
"""
import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except Exception:
    pass


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/test_asin_validation.py <client_id>")
        print("Example: python3 scripts/test_asin_validation.py 1")
        sys.exit(1)

    client_id = sys.argv[1].strip()
    if not client_id:
        print("Error: client_id is required")
        sys.exit(1)

    if not os.getenv("DATABASE_URL_PRODUCTION"):
        print("Warning: DATABASE_URL_PRODUCTION not set. Tests will use DB from .env or fail.")

    from src.core.asin_validator import (
        validate_asin_for_client,
        validate_asins_for_client,
        get_client_asins,
    )

    print("=" * 60)
    print("ASIN Validator tests (DB only, no LLM)")
    print("=" * 60)
    print(f"Client ID: {client_id}\n")

    # 1. Fetch client's ASINs
    print("1. get_client_asins(client_id) -> list of ASINs for this client")
    try:
        client_asins = get_client_asins(client_id)
        print(f"   Found {len(client_asins)} ASIN(s). First 5: {client_asins[:5]}")
    except Exception as e:
        print(f"   Error: {e}")
        client_asins = []

    # 2. Validate a fake ASIN (should be False)
    fake_asin = "B99INVALD0"
    print(f"\n2. validate_asin_for_client(client_id, '{fake_asin}')")
    try:
        ok = validate_asin_for_client(client_id, fake_asin)
        print(f"   Result: {ok} (expected False for invalid ASIN)")
    except Exception as e:
        print(f"   Error: {e}")

    # 3. validate_asins_for_client with mix
    test_asins = [fake_asin]
    if client_asins:
        test_asins.append(client_asins[0])
    print(f"\n3. validate_asins_for_client(client_id, {test_asins})")
    try:
        valid, invalid = validate_asins_for_client(client_id, test_asins)
        print(f"   valid_asins:   {valid}")
        print(f"   invalid_asins: {invalid}")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "=" * 60)
    print("Done. For full flow (invalid ASIN -> reply + client_asins), run:")
    print("  python3 scripts/test_intent_orchestrator.py --asin-validation --client-id", client_id)
    print("  or call POST /api/chat/message with a message containing an invalid ASIN.")
    print("=" * 60)


if __name__ == "__main__":
    main()
