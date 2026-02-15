#!/usr/bin/env python3
"""
Test script to validate multiple agent detection
Tests whether the LLM correctly identifies and returns multiple agents when requested
Run: python tests/test_multiple_agents.py
"""
import asyncio
import json
import os
import sys

# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.backend import my_chatbot_async

# Test cases: (query, expected_agent_count, description)
TEST_CASES = [
    # Two Agents
    ("I need to improve both my listing text and images", 2, "Two agents: text enhancement + image enhancement"),
    ("Can you help me create a listing and also check my images?", 2, "Two agents: listing creation + image checking"),
    ("I want to create A+ content and also track competitors", 2, "Two agents: A+ content + competition alerts"),
    ("Help me with text enhancement and banner creation", 2, "Two agents: text enhancement + banner generation"),
    
    # Three Agents
    ("I need to create a listing, improve my images, and track competitors", 3, "Three agents: listing + image + competition"),
    ("Can you help me with listing creation, text optimization, and A+ content?", 3, "Three agents: listing + text + A+ content"),
    ("I want to enhance my text, create lifestyle images, and generate banners", 3, "Three agents: text + lifestyle + banner"),
]

async def test_query(query, expected_count, description):
    """
    Test a single query and check if the correct number of agents is returned
    
    Args:
        query: The user query to test
        expected_count: Expected number of agents
        description: Description of what this test is checking
        
    Returns:
        dict with test results
    """
    try:
        result = await my_chatbot_async(
            language="English",
            freeform_text=query,
            chat_history=None
        )
        
        # Extract agentId from result
        agent_id = result.get('agentId')
        
        # Determine actual count
        if agent_id is None:
            actual_count = 0
            agent_ids = []
        elif isinstance(agent_id, list):
            actual_count = len(agent_id)
            agent_ids = agent_id
        elif isinstance(agent_id, str):
            actual_count = 1
            agent_ids = [agent_id]
        else:
            actual_count = 0
            agent_ids = []
        
        # Check if test passed
        passed = actual_count == expected_count
        
        return {
            'query': query,
            'description': description,
            'expected_count': expected_count,
            'actual_count': actual_count,
            'agent_ids': agent_ids,
            'intent': result.get('intent'),
            'passed': passed,
            'error': None
        }
        
    except Exception as e:
        return {
            'query': query,
            'description': description,
            'expected_count': expected_count,
            'actual_count': 0,
            'agent_ids': [],
            'intent': None,
            'passed': False,
            'error': str(e)
        }

async def run_all_tests():
    """Run all test cases and display results"""
    print("=" * 80)
    print("MULTIPLE AGENTS DETECTION TEST")
    print("=" * 80)
    print(f"\nTesting {len(TEST_CASES)} queries...\n")
    
    results = []
    
    for i, (query, expected_count, description) in enumerate(TEST_CASES, 1):
        print(f"[{i}/{len(TEST_CASES)}] Testing: {query}")
        print(f"  Expected: {expected_count} agent(s)")
        
        result = await test_query(query, expected_count, description)
        results.append(result)
        
        # Display immediate result
        if result['passed']:
            print(f"  ✅ PASSED - Found {result['actual_count']} agent(s): {result['agent_ids']}")
        else:
            print(f"  ❌ FAILED - Found {result['actual_count']} agent(s), expected {expected_count}")
            if result['agent_ids']:
                print(f"     Agents found: {result['agent_ids']}")
            if result['error']:
                print(f"     Error: {result['error']}")
        
        print()
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed_count = sum(1 for r in results if r['passed'])
    failed_count = len(results) - passed_count
    
    print(f"\nTotal Tests: {len(results)}")
    print(f"✅ Passed: {passed_count}")
    print(f"❌ Failed: {failed_count}")
    print(f"Success Rate: {(passed_count/len(results)*100):.1f}%")
    
    # Detailed results
    print("\n" + "=" * 80)
    print("DETAILED RESULTS")
    print("=" * 80)
    
    for i, result in enumerate(results, 1):
        status = "✅ PASS" if result['passed'] else "❌ FAIL"
        print(f"\n{i}. {status} - {result['description']}")
        print(f"   Query: \"{result['query']}\"")
        print(f"   Expected: {result['expected_count']} agent(s)")
        print(f"   Actual: {result['actual_count']} agent(s)")
        if result['agent_ids']:
            print(f"   Agent IDs: {result['agent_ids']}")
        print(f"   Intent: {result['intent']}")
        if result['error']:
            print(f"   Error: {result['error']}")
    
    # Show raw response for failed tests
    if failed_count > 0:
        print("\n" + "=" * 80)
        print("RAW RESPONSES FOR FAILED TESTS")
        print("=" * 80)
        
        for i, result in enumerate(results, 1):
            if not result['passed']:
                print(f"\n[{i}] Query: \"{result['query']}\"")
                try:
                    test_result = await my_chatbot_async(
                        language="English",
                        freeform_text=result['query'],
                        chat_history=None
                    )
                    raw_response = test_result.get('raw_response', '')
                    # Show last 300 chars where JSON usually is
                    print(f"   Last 300 chars of raw response:")
                    print(f"   {raw_response[-300:]}")
                except Exception as e:
                    print(f"   Error getting raw response: {e}")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETED")
    print("=" * 80)
    
    return results

if __name__ == "__main__":
    try:
        results = asyncio.run(run_all_tests())
        # Exit with error code if any tests failed
        exit_code = 0 if all(r['passed'] for r in results) else 1
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

