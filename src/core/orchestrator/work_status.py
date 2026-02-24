"""
Work Status – Marketplace Capability Finalizer

After user_intent enriches the query with ALL of the user's registered
marketplaces, this module checks which of those marketplaces are actually
operational ("available") for the detected category/capability.

It then:
  • removes unavailable marketplace mentions from the enriched query,
  • builds a user-facing notice (e.g. "Shopclues analytics integration
    is coming soon. Meanwhile, here are results from Amazon.in."),
  • returns the cleaned-up enriched query for downstream routing.

IMPORTANT — availability is checked per *individual* registered marketplace,
NOT per canonical key.  Amazon.in (available) and Amazon.com (in_development)
are treated as two separate platforms even though they share the canonical
key "amazon".

This is the *bridge* between user_intent and category routing — the
direct user_intent response should NOT be routed; work_status finalizes
it first.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from src.services.mp_validator import (
    extract_mentioned_marketplaces,
    _ALIAS_TO_CANONICAL,
    KNOWN_MARKETPLACES,
)
from utils.logger_config import get_logger

logger = get_logger(__name__)


# ── Platform capability matrix ────────────────────────────────────────────
# category → platform → {status: "available" | "in_development" | …}
# All marketplaces we currently give services to.
CAPABILITIES: Dict[str, Dict[str, Dict[str, str]]] = {
    "analytics_reporting": {
        "Amazon.in":           {"status": "available"},
        "Amazon.com":          {"status": "available"},
        "Amazon.co.uk":        {"status": "in_development"},
        "Amazon.ca":           {"status": "in_development"},
        "Amazon.com.mx":       {"status": "in_development"},
        "Amazon.ae":           {"status": "in_development"},
        "vendorcentral.amazon.com": {"status": "in_development"},
        "www.vendorcentral.in":     {"status": "in_development"},
        "Flipkart.com":        {"status": "in_development"},
        "Walmart.com":         {"status": "in_development"},
        "Shopify.com":         {"status": "in_development"},
        "Shopify.com/in":      {"status": "in_development"},
        "Shopify.in":          {"status": "in_development"},
        "Shopclues":           {"status": "in_development"},
        "Ondc":                {"status": "in_development"},
        "ebay.com":            {"status": "in_development"},
    },
    "insights_kb": {
        "Amazon.com": {"status": "available"},
        "Amazon.in":  {"status": "available"},
        "Amazon.co.uk":        {"status": "in_development"},
        "Amazon.ca":           {"status": "in_development"},
        "Amazon.com.mx":       {"status": "in_development"},
        "Amazon.ae":           {"status": "in_development"},
        "vendorcentral.amazon.com": {"status": "in_development"},
        "www.vendorcentral.in":     {"status": "in_development"},
        "Flipkart.com":        {"status": "in_development"},
        "Walmart.com":         {"status": "in_development"},
        "Shopify.com":         {"status": "in_development"},
        "Shopify.com/in":      {"status": "in_development"},
        "Shopify.in":          {"status": "in_development"},
        "Shopclues":           {"status": "in_development"},
        "Ondc":                {"status": "in_development"},
        "ebay.com":            {"status": "in_development"},
    },
}


# ── Public helpers (kept from original) ───────────────────────────────────

def get_available_capabilities() -> Dict[str, List[str]]:
    """
    Return only the *available* platforms for each capability.

    Example return:
        {"analytics_reporting": ["Amazon.in", "Shopify.in"],
         "insights_kb": ["Amazon.com"]}
    """
    available: Dict[str, List[str]] = {}
    for capability, platforms in CAPABILITIES.items():
        available[capability] = [
            platform
            for platform, details in platforms.items()
            if details.get("status") == "available"
        ]
    return available


# ── Internal helpers ──────────────────────────────────────────────────────

def _get_platform_status(mp_name: str, category_id: str) -> str:
    """
    Return the CAPABILITIES status for a specific marketplace platform
    within a category.

    Returns:
        ``"available"``      – platform is live for this category.
        ``"in_development"`` – platform is being built.
        ``"not_supported"``  – platform has no entry in CAPABILITIES
                               for this category (treat as unavailable).
    """
    if category_id not in CAPABILITIES:
        return "available"  # no capability gate for this category

    cap_platforms = CAPABILITIES[category_id]
    for cap_name, details in cap_platforms.items():
        if cap_name.strip().lower() == mp_name.strip().lower():
            return details.get("status", "not_supported")
    return "not_supported"


def _remove_name_from_text(text: str, name: str) -> str:
    """
    Remove one specific marketplace name from *text* with grammar-aware
    cleanup of surrounding commas / conjunctions.

    Returns the text with the first occurrence removed, or unchanged if
    the name was not found.
    """
    esc = re.escape(name)
    # Try patterns from most specific to least specific.
    patterns_replacements = [
        # ", name and …" → " and …"    (middle of comma + and list)
        (r',\s*' + esc + r'\s+and\s+', ' and '),
        # "… and name"                   (end of list)
        (r'\s+and\s+' + esc + r'(?=[\s.,!?\'\")?\]:]|$)', ''),
        # "name and …"                   (start of list)
        (esc + r'\s+and\s+', ''),
        # "name, …"                      (start, comma-separated)
        (esc + r'\s*,\s*', ''),
        # ", name"                        (end, comma-separated)
        (r',\s*' + esc, ''),
        # standalone name
        (esc, ''),
    ]
    for pattern, repl in patterns_replacements:
        new_text, n = re.subn(pattern, repl, text, count=1, flags=re.IGNORECASE)
        if n:
            return new_text
    return text


def _remove_canonical_aliases(text: str, canonical: str) -> str:
    """
    Remove ALL known aliases for a canonical key from the text.
    Used as a fallback when the LLM wrote a generic name (e.g. "Amazon")
    instead of the specific registered name (e.g. "Amazon.com").
    """
    aliases: List[str] = []
    for c, alias_list in KNOWN_MARKETPLACES:
        if c == canonical:
            aliases.extend(alias_list)
    # Longest first so "amazon.in" is tried before "amazon"
    aliases.sort(key=len, reverse=True)
    for alias in aliases:
        text = _remove_name_from_text(text, alias)
    return text


def _tidy_up_query(text: str) -> str:
    """Clean up grammar artefacts left after marketplace-name removal."""
    text = re.sub(r'\s{2,}', ' ', text)                                      # collapse spaces
    text = re.sub(r'\s+([.,!?])', r'\1', text)                               # space before punct
    text = re.sub(r'\b(across|on|from|for)\s*([.,!?])', r'\2', text)         # "across." → "."
    text = re.sub(r'\b(across|on|from|for)\s*$', '', text)                   # trailing preposition
    return text.strip()


def _build_availability_notice(
    category_id: str,
    unavailable_names: List[str],
    available_names: List[str],
) -> str:
    """Build a user-friendly notice about unavailable marketplaces."""
    label = {
        "analytics_reporting": "analytics",
        "insights_kb": "insights",
    }.get(category_id, category_id.replace("_", " "))

    if len(unavailable_names) == 1:
        notice = f"{unavailable_names[0]} {label} integration is coming soon."
    else:
        joined = ", ".join(unavailable_names[:-1]) + " and " + unavailable_names[-1]
        notice = f"{joined} {label} integrations are coming soon."

    if available_names:
        if len(available_names) == 1:
            notice += f" Meanwhile, here are results from {available_names[0]}."
        else:
            avail_joined = ", ".join(available_names[:-1]) + " and " + available_names[-1]
            notice += f" Meanwhile, here are results from {avail_joined}."

    return notice


# ── Public API ────────────────────────────────────────────────────────────

def finalize_enriched_query(
    category_id: str,
    enriched_query: str,
    marketplaces_registered: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Finalize the enriched query by checking marketplace availability for
    the detected category.

    **Each registered marketplace is checked individually against
    CAPABILITIES** — Amazon.in and Amazon.com are treated as separate
    platforms, even though they share the canonical key "amazon".

    Args:
        category_id:  Detected intent category (e.g. ``"analytics_reporting"``).
        enriched_query:  Enriched query from user_intent (may mention all
                         registered marketplace names).
        marketplaces_registered:  User's registered marketplace names from
                                  the request payload
                                  (e.g. ``["Amazon.in", "Amazon.com", "Flipkart"]``).

    Returns:
        Dict with keys:
            ``enriched_query``  – query with unavailable MP mentions removed.
            ``notice``          – user-facing notice string, or ``None``.
            ``available``       – list of available marketplace names.
            ``unavailable``     – list of unavailable marketplace names.
            ``all_unavailable`` – ``True`` when *every* mentioned MP is
                                  unavailable (caller may choose to short-circuit).
    """
    registered = marketplaces_registered or []

    # Categories not tracked in CAPABILITIES → pass through unchanged
    if category_id not in CAPABILITIES:
        return {
            "enriched_query": enriched_query,
            "notice": None,
            "available": [],
            "unavailable": [],
            "all_unavailable": False,
        }

    # Which canonical marketplace keys appear in the enriched query?
    mentioned_canonical = extract_mentioned_marketplaces(enriched_query)
    if not mentioned_canonical:
        return {
            "enriched_query": enriched_query,
            "notice": None,
            "available": [],
            "unavailable": [],
            "all_unavailable": False,
        }

    # ── Check each registered marketplace INDIVIDUALLY ────────────────
    available_mps: List[str] = []    # names whose status == "available"
    unavailable_mps: List[str] = []  # names whose status != "available"

    for mp_name in registered:
        canonical = _ALIAS_TO_CANONICAL.get(
            mp_name.strip().lower(), mp_name.strip().lower()
        )
        if canonical not in mentioned_canonical:
            continue  # this MP's canonical key isn't in the query at all

        status = _get_platform_status(mp_name, category_id)
        if status == "available":
            available_mps.append(mp_name)
        else:
            unavailable_mps.append(mp_name)

    # Nothing to filter → return unchanged
    if not unavailable_mps:
        return {
            "enriched_query": enriched_query,
            "notice": None,
            "available": available_mps,
            "unavailable": [],
            "all_unavailable": False,
        }

    # ── Remove each unavailable MP name from the enriched query ───────
    updated_query = enriched_query

    # Sort longest-first to avoid partial-match issues
    # (e.g. remove "Amazon.com" before a bare "Amazon" alias could match)
    for mp_name in sorted(unavailable_mps, key=len, reverse=True):
        updated_query = _remove_name_from_text(updated_query, mp_name)

    # Fallback: if the LLM used a generic alias (e.g. "Amazon") instead
    # of the specific registered name, the removal above would not have
    # matched.  Scan for any leftover canonical mentions that have NO
    # available variant and remove those generic aliases too.
    remaining_canonical = extract_mentioned_marketplaces(updated_query)
    for canonical in remaining_canonical:
        has_available_variant = any(
            _ALIAS_TO_CANONICAL.get(mp.strip().lower(), mp.strip().lower()) == canonical
            for mp in available_mps
        )
        if not has_available_variant:
            updated_query = _remove_canonical_aliases(updated_query, canonical)

    # Clean up grammar artefacts
    updated_query = _tidy_up_query(updated_query)

    # Build notice
    notice = _build_availability_notice(category_id, unavailable_mps, available_mps)

    all_unavailable = len(available_mps) == 0

    logger.info(
        "work_status finalized: available=%s, unavailable=%s, all_unavailable=%s",
        available_mps, unavailable_mps, all_unavailable,
    )
    logger.info("Enriched query updated: '%s' → '%s'", enriched_query, updated_query)
    logger.info("Notice: %s", notice)

    return {
        "enriched_query": updated_query,
        "notice": notice,
        "available": available_mps,
        "unavailable": unavailable_mps,
        "all_unavailable": all_unavailable,
    }
