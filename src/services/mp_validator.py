"""
Marketplace Validator

Validates that any marketplace mentioned in the user's query or in the enriched query
(from user_intent) is one of the marketplaces the user has registered (from payload).
If the user asks about a marketplace they are not registered for, returns a structured
error so the API can respond with "You have not registered this marketplace".
"""
from __future__ import annotations

import re
import difflib
from typing import Dict, List, Optional, Set, Tuple, Any

from utils.logger_config import get_logger

logger = get_logger(__name__)


# Canonical marketplace keys (lowercase) and their aliases for mention detection.
# Order matters for extraction: longer/compound names first (e.g. "Amazon.in" before "Amazon").
# All marketplaces we currently give services to.
KNOWN_MARKETPLACES: List[Tuple[str, List[str]]] = [
    ("amazon", [
        "vendorcentral.amazon.com", "www.vendorcentral.in",
        "amazon.in", "amazon.com", "amazon.co.uk", "amazon.ca",
        "amazon.com.mx", "amazon.ae", "amazon",
    ]),
    ("walmart", ["walmart.com", "walmart"]),
    ("shopify", ["shopify.com/in", "shopify.com", "shopify.in", "shopify"]),
    ("shopclues", ["shopclues", "shop clues"]),
    ("ondc", ["ondc"]),
    ("ebay", ["ebay.com", "ebay"]),
    ("flipkart", ["flipkart.com", "flipkart"]),
    ("meesho", ["meesho"]),
]

# Flatten: alias -> canonical key (lowercase)
_ALIAS_TO_CANONICAL: Dict[str, str] = {}
for canonical, aliases in KNOWN_MARKETPLACES:
    for a in aliases:
        _ALIAS_TO_CANONICAL[a.lower().strip()] = canonical


def _normalize_registered(marketplaces_registered: Optional[List[str]]) -> Set[str]:
    """
    Normalize payload marketplaces to a set of canonical keys (lowercase).
    E.g. ['Amazon.in', 'Flipkart'] -> {'amazon', 'flipkart'}.
    """
    if not marketplaces_registered or not isinstance(marketplaces_registered, list):
        return set()
    out: Set[str] = set()
    for m in marketplaces_registered:
        if not m or not isinstance(m, str):
            continue
        key = m.strip().lower()
        canonical = _ALIAS_TO_CANONICAL.get(key)
        if canonical:
            out.add(canonical)
        else:
            # Unknown name: treat the normalized string as its own canonical key
            out.add(key)
    return out


def get_marketplaces_registered_from_payload(payload_or_context: Optional[Dict[str, Any]]) -> List[str]:
    """
    Get the list of marketplaces the user is registered for from the request payload/context.

    Args:
        payload_or_context: Request context dict that may contain 'marketplaces_registered'
                            (list of strings, e.g. ['Amazon', 'Flipkart']).

    Returns:
        List of marketplace names as provided (empty list if missing or invalid).
    """
    if not payload_or_context or not isinstance(payload_or_context, dict):
        return []
    raw = payload_or_context.get("marketplaces_registered")
    if not isinstance(raw, list):
        return []
    return [str(m).strip() for m in raw if m is not None and str(m).strip()]


def extract_mentioned_marketplaces(text: str) -> Set[str]:
    """
    Extract marketplace names mentioned in a given text (user query or enriched query).
    Uses canonical keys (lowercase) so comparison with registered set is consistent.

    Args:
        text: Raw text to scan (e.g. "What is my Walmart sales?" or "sales across Amazon, ONDC and Flipkart").

    Returns:
        Set of canonical marketplace keys mentioned in text (e.g. {'walmart'}, {'amazon', 'ondc', 'flipkart'}).
    """
    if not text or not isinstance(text, str):
        return set()
    text_lower = text.lower()
    mentioned: Set[str] = set()
    alias_keys = set(_ALIAS_TO_CANONICAL.keys())

    # Prefer longer aliases first to avoid "amazon" matching inside "amazon.in"
    sorted_aliases = sorted(
        ((canonical, alias) for canonical, aliases in KNOWN_MARKETPLACES for alias in aliases),
        key=lambda x: -len(x[1])
    )

    for canonical, alias in sorted_aliases:
        # Word-boundary style: avoid matching inside words (e.g. "myamazon" or "amazonian")
        pattern = r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])"
        if re.search(pattern, text_lower):
            mentioned.add(canonical)

    # Fuzzy fallback: catch close spellings when regex did not match
    if alias_keys:
        tokens = [t for t in re.split(r"[^a-z0-9]+", text_lower) if len(t) >= 5]
        for token in tokens:
            match = difflib.get_close_matches(token, alias_keys, n=1, cutoff=0.86)
            if match:
                canonical = _ALIAS_TO_CANONICAL.get(match[0])
                if canonical:
                    mentioned.add(canonical)

    return mentioned


def validate_marketplace_access(
    user_query: str,
    enriched_query: str,
    marketplaces_registered: Optional[List[str]],
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Validate that every marketplace mentioned in the user query or the enriched query
    is in the user's registered marketplaces (from payload).

    Args:
        user_query: Original user message.
        enriched_query: Enriched query from user_intent (may include injected marketplaces).
        marketplaces_registered: List of marketplace names from payload (e.g. ['Amazon', 'Flipkart']).

    Returns:
        - (True, None) if valid: all mentioned marketplaces are registered.
        - (False, error_result) if invalid: at least one mentioned marketplace is not registered.
          error_result is a dict with 'reply' and optional keys for the API response.
    """
    registered_normalized = _normalize_registered(marketplaces_registered or [])
    from_user = extract_mentioned_marketplaces(user_query)
    from_enriched = extract_mentioned_marketplaces(enriched_query)
    all_mentioned = from_user | from_enriched

    if not all_mentioned:
        return True, None

    unregistered = all_mentioned - registered_normalized
    if not unregistered:
        return True, None

    # Map canonical key back to a display name for the message (optional)
    canonical_to_display = {}
    for canonical, aliases in KNOWN_MARKETPLACES:
        canonical_to_display[canonical] = aliases[0].title() if aliases else canonical
    names = [canonical_to_display.get(c, c.title()) for c in sorted(unregistered)]

    if len(names) == 1:
        reply = "You have not registered this marketplace. Kindly register and access your data."
    else:
        reply = "You have not registered these marketplaces: " + ", ".join(names) + ". Kindly register and access your data."

    logger.info(
        "Marketplace validation failed: mentioned=%s, registered=%s, unregistered=%s",
        list(all_mentioned),
        list(registered_normalized),
        list(unregistered),
    )

    return False, {
        "reply": "",  # Main reply left empty; message goes in notice
        "notice": reply,
        "intent": "marketplace_validation_failed",
        "agentId": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "category": "product_detail",
        "unregistered_marketplaces": list(unregistered),
    }


def validate_from_context(
    user_query: str,
    enriched_query: str,
    context: Optional[Dict[str, Any]],
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Convenience: run marketplace validation using marketplaces_registered from context.

    Args:
        user_query: Original user message.
        enriched_query: Enriched query from user_intent.
        context: Request context dict (payload) containing 'marketplaces_registered'.

    Returns:
        Same as validate_marketplace_access.
    """
    registered = get_marketplaces_registered_from_payload(context)
    return validate_marketplace_access(user_query, enriched_query, registered)
