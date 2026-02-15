#!/usr/bin/env python3
"""
Interactive test script to check backend output format
Run: python tests/test_backend_output.py
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

async def test_backend():
    # Default query
    default_query = "i need to refine my image and A+ content"
    
    print("=" * 80)
    print("TESTING BACKEND OUTPUT - Interactive Mode")
    print("=" * 80)
    print(f"\nDefault query: '{default_query}'")
    print("\nEnter your query (or press Enter to use default):")
    user_input = input("> ").strip()
    
    # Use default if empty input
    query = user_input if user_input else default_query
    
    print(f"\nUsing query: {query}\n")
    print("-" * 80)
    
    try:
        result = await my_chatbot_async(
            language="English",
            freeform_text=query,
            chat_history=None
        )
        
        print("\n📦 STRUCTURED RESPONSE (dict):")
        print("-" * 80)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        print("\n\n🔍 DETAILED BREAKDOWN:")
        print("-" * 80)
        print(f"Type of result: {type(result)}")
        print(f"Is dict: {isinstance(result, dict)}")
        
        if isinstance(result, dict):
            print(f"\nKeys in result: {list(result.keys())}")
            
            print(f"\n1. 'reply' (type: {type(result.get('reply'))}):")
            print(f"   Length: {len(result.get('reply', ''))} chars")
            print(f"   Preview: {result.get('reply', '')[:200]}...")
            
            print(f"\n2. 'intent' (type: {type(result.get('intent'))}):")
            print(f"   Value: {result.get('intent')}")
            
            print(f"\n3. 'agentId' (type: {type(result.get('agentId'))}):")
            print(f"   Value: {result.get('agentId')}")
            print(f"   Is None: {result.get('agentId') is None}")
            print(f"   Is List: {isinstance(result.get('agentId'), list)}")
            print(f"   Is String: {isinstance(result.get('agentId'), str)}")
            if result.get('agentId'):
                print(f"   Content: {result.get('agentId')}")
            
            print(f"\n4. 'raw_response' (type: {type(result.get('raw_response'))}):")
            raw = result.get('raw_response', '')
            print(f"   Length: {len(raw)} chars")
            print(f"   Last 500 chars (where JSON usually is):")
            print(f"   {raw[-500:]}")
        
        print("\n" + "=" * 80)
        print("✅ Test completed successfully!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\n" + "=" * 80)

if __name__ == "__main__":
    try:
        asyncio.run(test_backend())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()

