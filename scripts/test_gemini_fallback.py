"""
Manual test for Gemini fallback when Bedrock fails (any error).

Tests:
1. Mocked: Bedrock raises (e.g. ThrottlingException) -> fallback calls Gemini (mocked) -> returns (text, 0, 0).
2. Real (if GEMINI_API_KEY set): Bedrock mocked to fail -> real Gemini is called -> non-empty response.

Usage:
    # From project root (use same Python as main.py, e.g. python3.13)
    python3.13 scripts/test_gemini_fallback.py

    # With mocked Gemini only (no API key needed)
    python3.13 scripts/test_gemini_fallback.py --mock-only
"""

import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Load .env before importing backend
from dotenv import load_dotenv
load_dotenv(project_root / ".env")


def make_throttling_error():
    """Build a ClientError that looks like Bedrock ThrottlingException."""
    from botocore.exceptions import ClientError
    return ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Too many tokens, please wait before trying again."},
         "ResponseMetadata": {"HTTPStatusCode": 429}},
        "InvokeModel",
    )


def test_fallback_with_mocked_gemini():
    """When Bedrock fails (any error), fallback uses Gemini; with Gemini mocked we get (fake_text, 0, 0)."""
    from src.core.backend import invoke_llm_with_gemini_fallback

    fake_response = '{"category": "product_detail", "enriched_query": "What are your features?"}'

    with patch("src.core.backend._invoke_bedrock_with_tokens_impl", side_effect=make_throttling_error()):
        mock_response = MagicMock()
        mock_response.text = fake_response
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
            with patch("google.genai.Client", return_value=mock_client):

                text, in_tok, out_tok = invoke_llm_with_gemini_fallback(
                    model_id="mistral.mistral-large-2402-v1:0",
                    formatted_messages=[{"role": "user", "content": "What are your features?"}],
                    system_prompt="",
                    max_tokens=200,
                    temperature=0.1,
                    gemini_model_id="gemini-2.0-flash",
                )

                assert text == fake_response, f"Expected {fake_response!r}, got {text!r}"
                assert in_tok == 0 and out_tok == 0, f"Expected (0, 0) tokens, got ({in_tok}, {out_tok})"
                mock_client.models.generate_content.assert_called_once()
    print("[PASS] test_fallback_with_mocked_gemini: fallback returned (text, 0, 0) and called Gemini.")


def test_fallback_with_real_gemini():
    """If GEMINI_API_KEY is set: Bedrock mocked to fail -> real Gemini is used -> non-empty response."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[SKIP] test_fallback_with_real_gemini: GEMINI_API_KEY not set.")
        return

    from src.core.backend import invoke_llm_with_gemini_fallback

    with patch("src.core.backend._invoke_bedrock_with_tokens_impl", side_effect=make_throttling_error()):
        text, in_tok, out_tok = invoke_llm_with_gemini_fallback(
            model_id="mistral.mistral-large-2402-v1:0",
            formatted_messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            system_prompt="",
            max_tokens=50,
            temperature=0.0,
            gemini_model_id="gemini-2.0-flash",
        )

    assert isinstance(text, str) and len(text.strip()) > 0, f"Expected non-empty text, got {text!r}"
    assert in_tok == 0 and out_tok == 0
    print(f"[PASS] test_fallback_with_real_gemini: real Gemini returned {len(text)} chars, tokens=(0, 0).")
    print(f"       Response preview: {text.strip()[:120]}...")


def test_is_throttling_helpers():
    """_is_throttling recognizes ClientError ThrottlingException and 'too many tokens' message."""
    from src.core.backend import _is_throttling

    assert _is_throttling(make_throttling_error()) is True
    e = Exception("Too many tokens, please wait")
    assert _is_throttling(e) is True
    e2 = Exception("Connection timeout")
    assert _is_throttling(e2) is False
    print("[PASS] test_is_throttling_helpers: _is_throttling behaves correctly.")


def test_messages_to_prompt():
    """_messages_to_prompt builds a single string from system + messages."""
    from src.core.backend import _messages_to_prompt

    messages = [{"role": "user", "content": "Hello"}]
    out = _messages_to_prompt(messages, "You are a bot.")
    assert "You are a bot." in out and "[user]" in out and "Hello" in out
    print("[PASS] test_messages_to_prompt: prompt built correctly.")


def main():
    mock_only = "--mock-only" in sys.argv
    print("Testing Gemini fallback (Bedrock failure -> Gemini)...")
    print()

    test_is_throttling_helpers()
    test_messages_to_prompt()
    test_fallback_with_mocked_gemini()

    if not mock_only:
        test_fallback_with_real_gemini()
    else:
        print("[SKIP] Real Gemini test (--mock-only).")

    print()
    print("All selected tests passed.")


if __name__ == "__main__":
    main()
