"""
Test Script for User Intent Orchestrator

This script tests the intent classification, query enrichment, and ASIN extraction.

Features tested:
1. Intent Classification - Routing to:
   - product_detail: Platform features, capabilities, pricing, integrations
   - analytics_reporting: User's own data, metrics, reports
   - recommendation_engine: Recommendations, advice, improvements
   - insights_kb: Product category exploration, category insights
   - out_of_scope: Non-e-commerce (chit-chat, general knowledge)

2. Query Enrichment - Making queries complete and self-contained:
   - Follow-up resolution, marketplace context, pronoun resolution

3. ASIN Extraction - Any ASIN(s) in the user query are returned as a separate entity (asins list)
   for reuse by other components.

Usage:
    python scripts/test_intent_orchestrator.py
    python scripts/test_intent_orchestrator.py --enrichment   # Test enrichment only
    python scripts/test_intent_orchestrator.py --insights-kb # Test insights_kb + ASIN extraction
    python scripts/test_intent_orchestrator.py --category insights_kb
    python scripts/test_intent_orchestrator.py --all         # Classification + enrichment + insights_kb + flow

Output:
    Prints classification, enrichment, and extracted asins for each test query.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.orchestrator.user_intent import get_orchestrator
from utils.logger_config import get_logger

logger = get_logger(__name__)


# Test queries organized by expected category
# Based on examples from docs/future_dev.md

TEST_QUERIES = {
    "product_detail": [
        "How do I connect Amazon account?",
        "What features do you offer?",
        "Can you track inventory?",
        "What's the difference between Pro and Enterprise?",
        "Do you support Walmart?",
        "What marketplaces are supported?",
        "Tell me about your AI agents",
        "What can this platform do?",
    ],
    
    "analytics_reporting": [
        "What are my sales today?",
        "Show me my sales data",
        "How are my ads performing?",
        "What are my top selling products?",
        "Good morning! How's business?",
        "Show me my revenue this week",
        "What's my conversion rate?",
        "Which of my products are low on inventory?",
    ],

    "recommendation_engine": [
        "How can I improve my sales?",
        "Best practices for product listings?",
        "What should I do about low revenue?",
        "How do I reduce returns?",
        "Tips to increase conversion rate?",
    ],

    "insights_kb": [
        # Category-based
        "Tell me about Electronics",
        "Electronics",
        "What categories do you have for Laptops?",
        "Show me insights for Fashion",
        "Explore Footwear",
        "I want to see Gaming products",
        "What about Kitchen products?",
        "Insights for Luggage",
        "Categories under Home",
        "Show me Security products",
        "What do you have for Industrial?",
        "Tell me about RAM",
        "Motherboard insights",
        # ASIN-based
        "Insights for ASIN B08N5WRWNW",
        "Get insights for this product B0ABC123XY",
        "Show me insights for ASIN B09V3KXJPB",
        "What can you tell me about ASIN B07XYZ123?",
        "I need insights for product B08N5WRWNW",
    ],
    
    "out_of_scope": [
        "How's the weather today?",
        "Tell me a joke",
        "Who won the World Cup in 2022?",
        "Best recipe for chicken curry?",
    ],
}


# ============================================================================
# INSIGHTS_KB + ASIN EXTRACTION
# ============================================================================
# When the query contains ASIN(s), the classifier returns them in the "asins" list (separate entity).
# These cases assert category and that asins are extracted when present.

INSIGHTS_KB_TEST_CASES = [
    {
        "name": "insights_kb – category only (Electronics)",
        "query": "Tell me about Electronics",
        "expected_category": "insights_kb",
        "expected_asins": [],
    },
    {
        "name": "insights_kb – category only (Laptops)",
        "query": "Insights for Laptops",
        "expected_category": "insights_kb",
        "expected_asins": [],
    },
    {
        "name": "insights_kb – category only (Fashion)",
        "query": "Show me insights for Fashion",
        "expected_category": "insights_kb",
        "expected_asins": [],
    },
    {
        "name": "insights_kb – ASIN extracted",
        "query": "Insights for ASIN B08N5WRWNW",
        "expected_category": "insights_kb",
        "expected_asins": ["B08N5WRWNW"],
    },
    {
        "name": "insights_kb – ASIN (product ID)",
        "query": "Get insights for this product B0ABC123XY",
        "expected_category": "insights_kb",
        "expected_asins": ["B0ABC123XY"],
    },
    {
        "name": "insights_kb – ASIN (show me insights)",
        "query": "Show me insights for ASIN B09V3KXJPB",
        "expected_category": "insights_kb",
        "expected_asins": ["B09V3KXJPB"],
    },
    # ASIN in other categories – asins still extracted for reuse
    {
        "name": "product_detail – ASIN in query",
        "query": "What features do you have for product B08N5WRWNW?",
        "expected_category": "product_detail",
        "expected_asins": ["B08N5WRWNW"],
    },
]


# ============================================================================
# QUERY ENRICHMENT TEST CASES
# ============================================================================
# These test cases specifically test the query enrichment functionality:
# 1. Follow-up queries that need conversation context
# 2. Queries that need marketplace context injection
# 3. Complete queries that should remain unchanged

ENRICHMENT_TEST_CASES = [
    # ==== FOLLOW-UP QUERIES (need conversation history) ====
    {
        "name": "Follow-up: How many (after returns discussion)",
        "query": "How many?",
        "chat_history": [
            {"role": "user", "content": "Any of my orders returned?"},
            {"role": "assistant", "content": "Yes, you have orders that were returned."},
        ],
        "user_context": {"marketplaces_registered": ["Amazon"]},
        "expected_category": "analytics_reporting",
        "should_enrich": True,
        "enrichment_keywords": ["returned", "orders", "how many"],  # Keywords that should appear in enriched query
    },
    {
        "name": "Follow-up: What about last week",
        "query": "What about last week?",
        "chat_history": [
            {"role": "user", "content": "What are my sales today?"},
            {"role": "assistant", "content": "Your sales today are $5,432."},
        ],
        "user_context": {"marketplaces_registered": ["Amazon", "Flipkart"]},
        "expected_category": "analytics_reporting",
        "should_enrich": True,
        "enrichment_keywords": ["sales", "last week"],
    },
    {
        "name": "Follow-up: Tell me more",
        "query": "Tell me more",
        "chat_history": [
            {"role": "user", "content": "What agents do you have?"},
            {"role": "assistant", "content": "We have Smart Listing Agent, Image Grading Agent, and A+ Content Agent."},
        ],
        "user_context": {"marketplaces_registered": []},
        "expected_category": "product_detail",
        "should_enrich": True,
        "enrichment_keywords": ["agent", "more"],
    },
    {
        "name": "Follow-up: How can I improve it",
        "query": "How can I improve it?",
        "chat_history": [
            {"role": "user", "content": "What's my conversion rate?"},
            {"role": "assistant", "content": "Your conversion rate is 2.3%, which is below the category average of 4.5%."},
        ],
        "user_context": {"marketplaces_registered": ["Amazon"]},
        "expected_category": "recommendation_engine",
        "should_enrich": True,
        "enrichment_keywords": ["improve", "conversion"],
    },
    {
        "name": "Follow-up: Show me details",
        "query": "Show me details",
        "chat_history": [
            {"role": "user", "content": "Which products are low on inventory?"},
            {"role": "assistant", "content": "You have 5 products with low inventory: Widget A, Widget B, Widget C, Widget D, Widget E."},
        ],
        "user_context": {"marketplaces_registered": ["Amazon", "ONDC"]},
        "expected_category": "analytics_reporting",
        "should_enrich": True,
        "enrichment_keywords": ["inventory", "details", "products"],
    },
    
    # ==== MARKETPLACE CONTEXT INJECTION ====
    {
        "name": "Marketplace: Sales query with multiple marketplaces",
        "query": "What is my sales?",
        "chat_history": [],
        "user_context": {"marketplaces_registered": ["Amazon", "ONDC", "Flipkart"]},
        "expected_category": "analytics_reporting",
        "should_enrich": True,
        "enrichment_keywords": ["sales", "Amazon", "ONDC", "Flipkart"],
    },
    {
        "name": "Marketplace: Orders query with multiple marketplaces",
        "query": "How many orders do I have?",
        "chat_history": [],
        "user_context": {"marketplaces_registered": ["Amazon", "Walmart"]},
        "expected_category": "analytics_reporting",
        "should_enrich": True,
        "enrichment_keywords": ["orders", "Amazon", "Walmart"],
    },
    {
        "name": "Marketplace: Returns query with multiple marketplaces",
        "query": "Show my returns",
        "chat_history": [],
        "user_context": {"marketplaces_registered": ["Amazon", "Flipkart", "Meesho"]},
        "expected_category": "analytics_reporting",
        "should_enrich": True,
        "enrichment_keywords": ["returns", "Amazon", "Flipkart", "Meesho"],
    },
    {
        "name": "Marketplace: Inventory query with marketplaces",
        "query": "What's my inventory status?",
        "chat_history": [],
        "user_context": {"marketplaces_registered": ["Amazon", "ONDC"]},
        "expected_category": "analytics_reporting",
        "should_enrich": True,
        "enrichment_keywords": ["inventory", "Amazon", "ONDC"],
    },
    
    # ==== SINGLE MARKETPLACE (should NOT add others) ====
    {
        "name": "Single marketplace: No enrichment needed",
        "query": "What is my sales?",
        "chat_history": [],
        "user_context": {"marketplaces_registered": ["Amazon"]},
        "expected_category": "analytics_reporting",
        "should_enrich": False,  # Only one marketplace, no need to enrich
        "enrichment_keywords": ["sales"],
    },
    
    # ==== ALREADY SPECIFIC MARKETPLACE (should NOT add others) ====
    {
        "name": "Specific marketplace: Amazon already mentioned",
        "query": "What is my Amazon sales?",
        "chat_history": [],
        "user_context": {"marketplaces_registered": ["Amazon", "Flipkart", "ONDC"]},
        "expected_category": "analytics_reporting",
        "should_enrich": False,  # Already specific, don't add other marketplaces
        "enrichment_keywords": ["Amazon", "sales"],
    },
    {
        "name": "Specific marketplace: Flipkart already mentioned",
        "query": "Show my Flipkart orders",
        "chat_history": [],
        "user_context": {"marketplaces_registered": ["Amazon", "Flipkart"]},
        "expected_category": "analytics_reporting",
        "should_enrich": False,
        "enrichment_keywords": ["Flipkart", "orders"],
    },
    
    # ==== COMPLETE QUERIES (should remain unchanged) ====
    {
        "name": "Complete: Platform feature question",
        "query": "What AI agents do you have?",
        "chat_history": [],
        "user_context": {"marketplaces_registered": ["Amazon"]},
        "expected_category": "product_detail",
        "should_enrich": False,
        "enrichment_keywords": ["agents"],
    },
    {
        "name": "Complete: Recommendation / best practices",
        "query": "What are best practices for listing yoga mats on Amazon?",
        "chat_history": [],
        "user_context": {"marketplaces_registered": ["Amazon", "Flipkart"]},
        "expected_category": "recommendation_engine",
        "should_enrich": False,
        "enrichment_keywords": ["best practices", "listing", "yoga"],
    },
    {
        "name": "Complete: Product/platform feature request",
        "query": "Can you generate a title for my wireless Bluetooth headphones?",
        "chat_history": [],
        "user_context": {"marketplaces_registered": ["Amazon"]},
        "expected_category": "product_detail",
        "should_enrich": False,
        "enrichment_keywords": ["title", "headphones"],
    },
    
    # ==== COMBINED: Follow-up + Marketplace ====
    {
        "name": "Combined: Follow-up with marketplace context",
        "query": "And what about returns?",
        "chat_history": [
            {"role": "user", "content": "What are my sales?"},
            {"role": "assistant", "content": "Your total sales across all marketplaces is $45,000."},
        ],
        "user_context": {"marketplaces_registered": ["Amazon", "ONDC", "Flipkart"]},
        "expected_category": "analytics_reporting",
        "should_enrich": True,
        "enrichment_keywords": ["returns", "Amazon", "ONDC", "Flipkart"],
    },
]


# ============================================================================
# CONVERSATION FLOW TEST CASES  
# ============================================================================
# These simulate multi-turn conversations to test context handling

CONVERSATION_FLOW_TESTS = [
    {
        "name": "Analytics → Follow-up → Recommendation",
        "turns": [
            {
                "query": "What are my returns?",
                "expected_category": "analytics_reporting",
            },
            {
                "query": "How many?",
                "expected_category": "analytics_reporting",
                "should_enrich": True,
            },
            {
                "query": "How can I reduce them?",
                "expected_category": "recommendation_engine",
                "should_enrich": True,
            },
        ],
        "user_context": {"marketplaces_registered": ["Amazon", "Flipkart"]},
    },
    {
        "name": "Sales inquiry with marketplace context",
        "turns": [
            {
                "query": "What is my sales?",
                "expected_category": "analytics_reporting",
                "should_enrich": True,  # Should add marketplaces
            },
            {
                "query": "Compare it to last month",
                "expected_category": "analytics_reporting",
                "should_enrich": True,
            },
        ],
        "user_context": {"marketplaces_registered": ["Amazon", "ONDC", "Flipkart"]},
    },
]


def print_results_table(results):
    """Print results in a formatted table."""
    print("\n" + "="*120)
    print("TEST RESULTS SUMMARY")
    print("="*120)
    print(f"{'Query':<50} {'Expected':<20} {'Actual':<20} {'Match':<10}")
    print("-"*120)
    
    matches = 0
    total = 0
    
    for query, expected, actual in results:
        total += 1
        match = "✅" if expected == actual else "❌"
        if expected == actual:
            matches += 1
        # Truncate long queries
        query_display = query[:47] + "..." if len(query) > 50 else query
        print(f"{query_display:<50} {expected:<20} {actual:<20} {match:<10}")
    
    print("-"*120)
    accuracy = (matches / total * 100) if total > 0 else 0
    print(f"\nAccuracy: {matches}/{total} ({accuracy:.1f}%)")
    print("="*120)


def print_enrichment_results(results):
    """Print enrichment test results."""
    print("\n" + "="*120)
    print("ENRICHMENT TEST RESULTS")
    print("="*120)
    
    passed = 0
    failed = 0
    
    for result in results:
        name = result["name"]
        query = result["query"]
        expected_cat = result["expected_category"]
        actual_cat = result["actual_category"]
        enriched = result["enriched_query"]
        should_enrich = result["should_enrich"]
        was_enriched = result["was_enriched"]
        keywords_found = result.get("keywords_found", [])
        keywords_missing = result.get("keywords_missing", [])
        
        # Check if test passed
        category_match = expected_cat == actual_cat
        enrichment_match = should_enrich == was_enriched
        keywords_ok = len(keywords_missing) == 0
        
        test_passed = category_match and (not should_enrich or keywords_ok)
        
        if test_passed:
            passed += 1
            status = "✅ PASS"
        else:
            failed += 1
            status = "❌ FAIL"
        
        print(f"\n{status} | {name}")
        print(f"   Query: \"{query}\"")
        print(f"   Category: {actual_cat} (expected: {expected_cat}) {'✓' if category_match else '✗'}")
        print(f"   Enriched: \"{enriched}\"")
        print(f"   Was enriched: {was_enriched} (expected: {should_enrich}) {'✓' if enrichment_match else '✗'}")
        if keywords_found:
            print(f"   Keywords found: {keywords_found}")
        if keywords_missing:
            print(f"   Keywords MISSING: {keywords_missing}")
    
    print("\n" + "-"*120)
    total = passed + failed
    accuracy = (passed / total * 100) if total > 0 else 0
    print(f"Enrichment Tests: {passed}/{total} passed ({accuracy:.1f}%)")
    print("="*120)


async def test_orchestrator():
    """Test the orchestrator with all test queries."""
    print("Initializing Orchestrator...")
    orchestrator = get_orchestrator()
    
    results = []
    
    # Test each category
    for category, queries in TEST_QUERIES.items():
        print(f"\n{'='*100}")
        print(f"Testing Category: {category.upper()}")
        print(f"{'='*100}")
        
        for query in queries:
            try:
                # Get classification from orchestrator (returns category, enriched_query, asins)
                classified_category, enriched_query, asins = await orchestrator.find_user_intent(query)
                
                # Store result
                results.append((query, category, classified_category))
                
                # Print individual result
                status = "✅" if category == classified_category else "❌"
                print(f"{status} Query: {query}")
                print(f"   Expected: {category} | Actual: {classified_category}")
                if enriched_query != query:
                    print(f"   Enriched: {enriched_query}")
                if asins:
                    print(f"   ASINs: {asins}")
                
            except Exception as e:
                logger.error(f"Error processing query '{query}': {e}", exc_info=True)
                results.append((query, category, f"ERROR: {str(e)}"))
                print(f"❌ Query: {query}")
                print(f"   Error: {str(e)}")
    
    # Print summary table
    print_results_table(results)
    
    # Category-wise breakdown
    print("\n" + "="*100)
    print("CATEGORY-WISE ACCURACY")
    print("="*100)
    
    for category in ["product_detail", "analytics_reporting", "recommendation_engine", "insights_kb", "out_of_scope"]:
        category_results = [r for r in results if r[1] == category]
        if category_results:
            matches = sum(1 for r in category_results if r[1] == r[2])
            total = len(category_results)
            accuracy = (matches / total * 100) if total > 0 else 0
            print(f"{category:<30} {matches}/{total} ({accuracy:.1f}%)")
    
    print("="*100)
    
    return results


async def test_enrichment():
    """Test the query enrichment functionality."""
    print("\n" + "="*120)
    print("TESTING QUERY ENRICHMENT")
    print("="*120)
    
    orchestrator = get_orchestrator()
    results = []
    
    for test_case in ENRICHMENT_TEST_CASES:
        name = test_case["name"]
        query = test_case["query"]
        chat_history = test_case.get("chat_history", [])
        user_context = test_case.get("user_context", {})
        expected_category = test_case["expected_category"]
        should_enrich = test_case["should_enrich"]
        enrichment_keywords = test_case.get("enrichment_keywords", [])
        
        print(f"\nTesting: {name}")
        print(f"   Query: \"{query}\"")
        if chat_history:
            print(f"   Chat history: {len(chat_history)} messages")
        if user_context.get("marketplaces_registered"):
            print(f"   Marketplaces: {user_context['marketplaces_registered']}")
        
        try:
            # Call find_user_intent with full context (returns category, enriched_query, asins)
            actual_category, enriched_query, _ = await orchestrator.find_user_intent(
                user_message=query,
                chat_history=chat_history,
                user_context=user_context
            )
            
            # Check if query was enriched
            was_enriched = enriched_query.lower() != query.lower()
            
            # Check for expected keywords in enriched query
            enriched_lower = enriched_query.lower()
            keywords_found = [kw for kw in enrichment_keywords if kw.lower() in enriched_lower]
            keywords_missing = [kw for kw in enrichment_keywords if kw.lower() not in enriched_lower]
            
            # Store result
            result = {
                "name": name,
                "query": query,
                "expected_category": expected_category,
                "actual_category": actual_category,
                "enriched_query": enriched_query,
                "should_enrich": should_enrich,
                "was_enriched": was_enriched,
                "keywords_found": keywords_found,
                "keywords_missing": keywords_missing,
            }
            results.append(result)
            
            # Print result
            category_status = "✓" if actual_category == expected_category else "✗"
            print(f"   Category: {actual_category} {category_status}")
            print(f"   Enriched: \"{enriched_query}\"")
            
            if was_enriched:
                print(f"   ✓ Query was enriched")
            else:
                print(f"   - Query unchanged")
            
            if keywords_missing and should_enrich:
                print(f"   ⚠ Missing keywords: {keywords_missing}")
                
        except Exception as e:
            logger.error(f"Error in enrichment test '{name}': {e}", exc_info=True)
            results.append({
                "name": name,
                "query": query,
                "expected_category": expected_category,
                "actual_category": "ERROR",
                "enriched_query": str(e),
                "should_enrich": should_enrich,
                "was_enriched": False,
                "keywords_found": [],
                "keywords_missing": enrichment_keywords,
            })
            print(f"   ❌ Error: {str(e)}")
    
    # Print summary
    print_enrichment_results(results)
    
    return results


async def test_conversation_flow():
    """Test multi-turn conversation flows."""
    print("\n" + "="*120)
    print("TESTING CONVERSATION FLOWS")
    print("="*120)
    
    orchestrator = get_orchestrator()
    
    for flow_test in CONVERSATION_FLOW_TESTS:
        flow_name = flow_test["name"]
        turns = flow_test["turns"]
        user_context = flow_test.get("user_context", {})
        
        print(f"\n{'='*80}")
        print(f"Flow: {flow_name}")
        print(f"Marketplaces: {user_context.get('marketplaces_registered', [])}")
        print(f"{'='*80}")
        
        # Build up chat history through turns
        chat_history = []
        
        for i, turn in enumerate(turns):
            query = turn["query"]
            expected_category = turn["expected_category"]
            should_enrich = turn.get("should_enrich", False)
            
            print(f"\n  Turn {i+1}: \"{query}\"")
            
            try:
                actual_category, enriched_query, asins = await orchestrator.find_user_intent(
                    user_message=query,
                    chat_history=chat_history,
                    user_context=user_context
                )
                
                was_enriched = enriched_query.lower() != query.lower()
                category_match = actual_category == expected_category
                
                status = "✓" if category_match else "✗"
                print(f"    Category: {actual_category} {status} (expected: {expected_category})")
                print(f"    Enriched: \"{enriched_query}\"")
                if asins:
                    print(f"    ASINs: {asins}")
                
                if should_enrich and was_enriched:
                    print(f"    ✓ Query was enriched as expected")
                elif should_enrich and not was_enriched:
                    print(f"    ⚠ Expected enrichment but query unchanged")
                
                # Add to chat history for next turn
                chat_history.append({"role": "user", "content": query})
                chat_history.append({"role": "assistant", "content": f"[Response to: {enriched_query}]"})
                
            except Exception as e:
                print(f"    ❌ Error: {str(e)}")
                break


async def test_insights_kb_extras():
    """Test that insights_kb and ASIN extraction work: category routing and asins list."""
    print("\n" + "="*120)
    print("TESTING INSIGHTS_KB + ASIN EXTRACTION")
    print("="*120)
    
    orchestrator = get_orchestrator()
    passed = 0
    failed = 0
    
    for test_case in INSIGHTS_KB_TEST_CASES:
        name = test_case["name"]
        query = test_case["query"]
        expected_category = test_case["expected_category"]
        expected_asins = test_case.get("expected_asins", [])
        expected_asin_set = {a.upper().strip() for a in expected_asins}
        
        print(f"\n  Test: {name}")
        print(f"  Query: \"{query}\"")
        
        try:
            actual_category, enriched_query, asins = await orchestrator.find_user_intent(query)
            actual_asin_set = {a.upper().strip() for a in asins} if asins else set()
            
            category_ok = actual_category == expected_category
            asins_ok = expected_asin_set == actual_asin_set
            
            test_passed = category_ok and asins_ok
            if test_passed:
                passed += 1
                status = "✅ PASS"
            else:
                failed += 1
                status = "❌ FAIL"
            
            print(f"  {status}")
            print(f"    Category: {actual_category} (expected: {expected_category}) {'✓' if category_ok else '✗'}")
            print(f"    ASINs: {asins} (expected: {expected_asins}) {'✓' if asins_ok else '✗'}")
            if not asins_ok:
                print(f"    Missing: {expected_asin_set - actual_asin_set}, Unexpected: {actual_asin_set - expected_asin_set}")
                
        except Exception as e:
            failed += 1
            print(f"  ❌ FAIL - Error: {e}")
            logger.exception(e)
    
    total = passed + failed
    pct = (passed / total * 100) if total else 0
    print("\n" + "-"*120)
    print(f"Insights KB + ASIN extraction: {passed}/{total} passed ({pct:.1f}%)")
    print("="*120)
    return passed, failed


# ============================================================================
# ASIN VALIDATION FLOW TEST
# ============================================================================
# When the user sends a message with an ASIN that does NOT belong to their
# client_id, the orchestrator should return intent "asin_validation_failed",
# invalid_asins, and client_asins (list of their actual ASINs from DB).


async def test_asin_validation_flow(client_id: str):
    """
    Test the full ASIN validation flow: invalid ASIN in query -> validation fails -> response
    includes client_asins and message asking user to select/enter correct ASIN.

    Requires:
      - DATABASE_URL_PRODUCTION set (for asin_validator DB)
      - client_id: a real client ID that has rows in amazon.product_asin
    Use an ASIN in the query that is NOT in that client's catalog so validation fails.
    """
    print("\n" + "="*120)
    print("TESTING ASIN VALIDATION FLOW (invalid ASIN -> client_asins in response)")
    print("="*120)
    print(f"Using client_id: {client_id}")
    print("Query: message containing an ASIN that does NOT belong to this client")
    print()

    orchestrator = get_orchestrator()
    # Use an ASIN that is NOT in the client's catalog so validation fails and we get asin_validation_failed.
    # Do not use a real ASIN for this client (e.g. B09T3ML6QY may be valid for client 48).
    invalid_asin_query = "Show me insights for ASIN B99INVALD0"
    context = {
        "userId": client_id,
        "user_id": client_id,
        "marketplaces_registered": ["Amazon"],
        "username": "TestUser",
    }
    chat_history = []

    try:
        result = await orchestrator.process_query(
            user_message=invalid_asin_query,
            chat_history=chat_history,
            context=context,
        )
    except Exception as e:
        logger.exception(e)
        print(f"❌ process_query failed: {e}")
        return False

    intent = result.get("intent")
    invalid_asins = result.get("invalid_asins", [])
    client_asins = result.get("client_asins", [])
    reply = result.get("reply", "")

    # Expect validation to have run and failed (invalid ASIN)
    if intent != "asin_validation_failed":
        print(f"❌ Expected intent 'asin_validation_failed', got: {intent}")
        print(f"   Reply: {reply[:200]}...")
        return False

    if "B99INVALD0" not in str(invalid_asins) and "b99invald0" not in str(invalid_asins).lower():
        print(f"❌ Expected invalid_asins to contain extracted ASIN (B99INVALD0), got: {invalid_asins}")
        return False

    print("✅ Intent is 'asin_validation_failed'")
    print(f"   invalid_asins: {invalid_asins}")
    print(f"   client_asins count: {len(client_asins)}")
    if client_asins:
        print(f"   client_asins (first 10): {client_asins[:10]}")
    print(f"   Reply (first 300 chars): {reply[:300]}...")
    print()
    print("="*120)
    print("ASIN validation flow test PASSED")
    print("="*120)
    return True


async def test_specific_queries(queries):
    """Test specific queries (useful for debugging)."""
    print("\nTesting Specific Queries...")
    orchestrator = get_orchestrator()
    
    for query in queries:
        try:
            # Returns (category, enriched_query, asins)
            classified_category, enriched_query, asins = await orchestrator.find_user_intent(query)
            print(f"\nQuery: {query}")
            print(f"Classified as: {classified_category}")
            print(f"Enriched to: {enriched_query}")
            if asins:
                print(f"ASINs: {asins}")
        except Exception as e:
            print(f"\nQuery: {query}")
            print(f"Error: {str(e)}")


def main():
    """Main function to run tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test User Intent Orchestrator with Classification and Enrichment")
    parser.add_argument(
        "--specific",
        nargs="+",
        help="Test specific queries instead of full test suite"
    )
    parser.add_argument(
        "--category",
        choices=["product_detail", "analytics_reporting", "recommendation_engine", "insights_kb", "out_of_scope"],
        help="Test only a specific category"
    )
    parser.add_argument(
        "--enrichment",
        action="store_true",
        help="Run query enrichment tests only"
    )
    parser.add_argument(
        "--flow",
        action="store_true",
        help="Run conversation flow tests only"
    )
    parser.add_argument(
        "--insights-kb",
        action="store_true",
        help="Run insights_kb tests (category_name vs asin_id JSON response)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all tests (classification + enrichment + insights_kb + flow)"
    )
    parser.add_argument(
        "--asin-validation",
        action="store_true",
        help="Test ASIN validation flow: invalid ASIN in query -> response with client_asins"
    )
    parser.add_argument(
        "--client-id",
        type=str,
        default=os.environ.get("TEST_CLIENT_ID", ""),
        help="Client ID for ASIN validation test (default: env TEST_CLIENT_ID)"
    )
    
    args = parser.parse_args()
    
    try:
        if args.specific:
            # Test specific queries
            asyncio.run(test_specific_queries(args.specific))
        elif args.category:
            # Test specific category
            category_queries = TEST_QUERIES.get(args.category, [])
            asyncio.run(test_specific_queries(category_queries))
        elif args.enrichment:
            # Run enrichment tests only
            asyncio.run(test_enrichment())
        elif args.flow:
            # Run conversation flow tests only
            asyncio.run(test_conversation_flow())
        elif args.insights_kb:
            # Run insights_kb category_name/asin_id tests only
            asyncio.run(test_insights_kb_extras())
        elif args.asin_validation:
            if not args.client_id or not str(args.client_id).strip():
                print("❌ ASIN validation test requires a client ID. Set --client-id 123 or env TEST_CLIENT_ID=123")
                print("   Use a client_id that has rows in amazon.product_asin.")
                sys.exit(1)
            asyncio.run(test_asin_validation_flow(str(args.client_id).strip()))
        elif args.all:
            # Run all tests
            async def run_all():
                print("\n" + "="*120)
                print("RUNNING ALL TESTS")
                print("="*120)
                
                print("\n\n📋 PART 1: CLASSIFICATION TESTS")
                await test_orchestrator()
                
                print("\n\n🔄 PART 2: ENRICHMENT TESTS")
                await test_enrichment()
                
                print("\n\n📂 PART 3: INSIGHTS_KB + ASIN EXTRACTION")
                await test_insights_kb_extras()
                
                print("\n\n💬 PART 4: CONVERSATION FLOW TESTS")
                await test_conversation_flow()
                
                print("\n\n" + "="*120)
                print("ALL TESTS COMPLETED")
                print("="*120)
            
            asyncio.run(run_all())
        else:
            # Default: run classification tests
            asyncio.run(test_orchestrator())
            
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        print(f"\n❌ Test failed: {str(e)}")


if __name__ == "__main__":
    main()

