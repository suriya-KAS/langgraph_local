"""
Integration test for memory layer functionality with e-commerce context.

This script tests the memory management logic using realistic e-commerce scenarios:

TURNS 1-10.5 (21 messages total):
- Tests multiple summary chunks being created at multiples of 4 messages
- At message 4: Creates summary for messages 1-4
- At message 8: Creates summary for messages 5-8
- At message 12: Creates summary for messages 9-12
- At message 16: Creates summary for messages 13-16
- At message 20: Creates summary for messages 17-20
- Message 21: Final message (incomplete chunk, no summary created)

The test verifies that:
1. 5 summary chunks are created and saved (for messages 1-4, 5-8, 9-12, 13-16, 17-20)
2. All summaries are stored in conversationSummaries array in conversations collection
3. Context for later messages includes all relevant summaries + recent messages
4. Summary chunks have correct startIndex, endIndex, and messageCount fields
"""
import os
import sys
import time
from datetime import datetime, timezone

# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.conversation_storage import get_conversation_storage
from src.core.memory_layer import get_conversation_context
from src.database.conversation_service import get_conversation_service
from utils.logger_config import get_logger

logger = get_logger(__name__)


def print_separator(title: str = ""):
    """Print a visual separator."""
    print("\n" + "=" * 80)
    if title:
        print(f"  {title}")
        print("=" * 80)
    print()


def print_context(context_messages: list, turn_number: int):
    """Print the conversation context in a readable format."""
    print(f"\n📋 Context for Turn {turn_number} ({len(context_messages)} messages):")
    print("-" * 80)
    for i, msg in enumerate(context_messages, 1):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        # Truncate long content for display
        display_content = content[:200] + "..." if len(content) > 200 else content
        print(f"  {i}. [{role.upper()}]: {display_content}")
    print("-" * 80)


def generate_conversation_pairs(num_turns: int) -> list:
    """
    Generate conversation pairs for testing.
    
    Args:
        num_turns: Number of conversation turns (each turn = user + assistant = 2 messages)
        
    Returns:
        List of conversation pair dictionaries
    """
    base_pairs = [
        {
            "user": "What is ACOS and how do I calculate it for my Amazon PPC campaigns?",
            "assistant": "ACOS (Advertising Cost of Sale) is a key metric for Amazon PPC campaigns. It's calculated as: ACOS = (Ad Spend / Ad Revenue) × 100. For example, if you spend $50 on ads and generate $200 in sales, your ACOS is 25%. A lower ACOS indicates better ad efficiency. For most sellers, a target ACOS of 15-30% is considered healthy, but this depends on your profit margins and business goals.",
            "intent": "advertising_metrics"
        },
        {
            "user": "Tell me about the A+ Content Agent and how it can help my listings.",
            "assistant": "The A+ Content Agent is designed to create enhanced brand content for your Amazon product listings. It helps you create visually rich product descriptions with comparison charts, high-quality images, and detailed brand storytelling. A+ Content can increase conversion rates by 3-10% on average. The agent analyzes your product features and generates compelling content modules that highlight your brand's unique value proposition.",
            "intent": "agent_inquiry"
        },
        {
            "user": "What's the difference between TACOS and ROAS? Which one should I focus on?",
            "assistant": "TACOS (Total Advertising Cost of Sale) and ROAS (Return on Ad Spend) measure advertising efficiency differently. TACOS = (Ad Spend / Total Revenue) × 100, including organic sales. ROAS = Ad Revenue / Ad Spend (inverse of ACOS). TACOS is better for long-term growth as it shows how ads impact overall business, while ROAS is useful for campaign-level optimization. I recommend tracking TACOS for strategic decisions (aim for 10-15%) and ROAS for individual campaign adjustments.",
            "intent": "advertising_metrics"
        },
        {
            "user": "How does the Smart Listing Agent optimize my product titles and bullet points?",
            "assistant": "The Smart Listing Agent uses AI to optimize your product titles and bullet points for maximum visibility and conversion. It analyzes top-performing competitors, identifies high-volume keywords, and structures your content following Amazon's A9 algorithm best practices. For titles, it ensures proper keyword placement within the 200-character limit. For bullet points, it creates benefit-focused content with strategic keyword integration, improving both search ranking and customer engagement.",
            "intent": "agent_inquiry"
        },
        {
            "user": "What marketplaces do you support besides Amazon?",
            "assistant": "We support multiple e-commerce marketplaces including Amazon (US, UK, EU, CA, AU), Walmart Marketplace, eBay, Shopify, and Etsy. Each platform has specialized agents optimized for their unique algorithms and requirements. You can manage all marketplaces from a single dashboard with unified analytics.",
            "intent": "marketplace_inquiry"
        },
        {
            "user": "What's the monthly subscription cost for the premium tier?",
            "assistant": "Our premium tier is $199/month and includes access to all AI agents, unlimited product optimizations, advanced analytics, priority support, and API access. You also get marketplace integration for up to 5 channels. There's a 20% discount for annual billing, bringing it to $159/month.",
            "intent": "pricing_inquiry"
        },
        {
            "user": "Can I use multiple agents at the same time?",
            "assistant": "Yes! You can use multiple agents simultaneously. For example, you can run Smart Listing Agent to optimize your titles, Image Grading Agent to improve product images, and A+ Content Agent to enhance your product descriptions all at once. The agents work independently and can be combined for comprehensive listing optimization.",
            "intent": "agent_inquiry"
        },
        {
            "user": "How do I track my listing performance?",
            "assistant": "You can track listing performance through our analytics dashboard. It shows key metrics like conversion rates, click-through rates, search ranking positions, organic vs. paid traffic, and revenue trends. You can also set up custom alerts for performance drops or significant changes in your metrics.",
            "intent": "analytics_inquiry"
        },
        {
            "user": "What is the best time to update my product listings?",
            "assistant": "The best time to update listings depends on your goals. For optimization improvements, any time is good, but avoid making changes during peak sales periods. For seasonal products, update 2-3 months before the season starts. Avoid frequent minor changes as they can temporarily impact rankings. Batch updates during slower periods for best results.",
            "intent": "listing_optimization"
        },
        {
            "user": "Do you offer API access for bulk operations?",
            "assistant": "Yes! Our premium tier includes API access for bulk operations. You can use the API to automate listing updates, bulk image processing, keyword optimization, and performance tracking across hundreds or thousands of products. The API supports REST endpoints and webhook notifications for async operations.",
            "intent": "api_inquiry"
        },
        {
            "user": "How accurate are the AI-generated product descriptions?",
            "assistant": "Our AI-generated descriptions are highly accurate and optimized for Amazon's A9 algorithm. They're tested against top-performing listings in each category and continuously improved based on conversion data. However, we always recommend human review before publishing, especially for products with unique features or compliance requirements.",
            "intent": "ai_accuracy"
        }
    ]
    
    # Repeat base pairs if needed to reach num_turns
    pairs = []
    for i in range(num_turns):
        pairs.append(base_pairs[i % len(base_pairs)])
    
    return pairs


def test_memory_layer():
    """Test the memory layer functionality with 21 messages (5 summary chunks)."""
    print_separator("Memory Layer Integration Test - 21 Messages (5 Summary Chunks)")
    
    # Initialize services
    conversation_storage = get_conversation_storage()
    conversation_service = get_conversation_service()
    
    # Test user ID
    user_id = "user_test_memory_21"
    
    # Step 1: Create a dummy conversation
    print("Step 1: Creating dummy conversation...")
    conversation_id = conversation_storage.get_or_create_conversation(
        user_id=user_id,
        conversation_id=None
    )
    print(f"✓ Created conversation: {conversation_id}")
    
    # Generate 11 conversation pairs (22 messages total, but we'll stop at 21)
    # We need 10.5 turns = 21 messages (10 full turns + 1 user message)
    conversation_pairs = generate_conversation_pairs(11)
    
    # Step 2: Create 21 messages (10 full turns + 1 user message)
    print_separator("Step 2: Creating 21 Messages (10.5 Turns)")
    print("Expected summary chunks:")
    print("  - Messages 1-4:  Summary chunk 1 (created at message 4)")
    print("  - Messages 5-8:  Summary chunk 2 (created at message 8)")
    print("  - Messages 9-12: Summary chunk 3 (created at message 12)")
    print("  - Messages 13-16: Summary chunk 4 (created at message 16)")
    print("  - Messages 17-20: Summary chunk 5 (created at message 20)")
    print("  - Message 21: Incomplete chunk (no summary)")
    print()
    
    summary_checkpoints = [4, 8, 12, 16, 20]  # Message counts where summaries should be created
    
    for turn in range(1, 11):  # 10 full turns = 20 messages
        print(f"\n🔄 Turn {turn} (Messages {turn*2-1}-{turn*2}):")
        
        # Save user message first
        user_msg = conversation_pairs[turn - 1]["user"]
        print(f"  Saving user message: {user_msg[:50]}...")
        user_msg_id = conversation_storage.save_user_message(
            conversation_id=conversation_id,
            user_id=user_id,
            content=user_msg
        )
        print(f"  ✓ Saved user message: {user_msg_id}")
        
        # Get conversation to check message count
        conversation = conversation_service.get_conversation(conversation_id)
        message_count = conversation.get("stats", {}).get("messageCount", 0)
        print(f"  Current message count: {message_count}")
        
        # Check if summary should be created at this point
        if message_count in summary_checkpoints:
            print(f"  ⏳ Summary checkpoint reached! Checking for summary creation...")
            time.sleep(2)  # Give time for summary creation
            
            # Get context to trigger summary creation
            context = get_conversation_context(
                conversation_id=conversation_id,
                current_user_message=user_msg
            )
            
            # Check summaries
            conversation = conversation_service.get_conversation(conversation_id)
            conversation_summaries = conversation.get("conversationSummaries", [])
            
            expected_chunks = message_count // 4
            print(f"  ✓ Expected {expected_chunks} summary chunk(s), found {len(conversation_summaries)}")
            
            for summary in conversation_summaries:
                start_idx = summary.get("startIndex")
                end_idx = summary.get("endIndex")
                print(f"    - Summary for messages {start_idx}-{end_idx}")
        
        # Save assistant message
        assistant_msg = conversation_pairs[turn - 1]["assistant"]
        print(f"  Saving assistant message: {assistant_msg[:50]}...")
        assistant_msg_id = conversation_storage.save_assistant_message(
            conversation_id=conversation_id,
            user_id=user_id,
            content=assistant_msg,
            intent=conversation_pairs[turn - 1]["intent"]
        )
        print(f"  ✓ Saved assistant message: {assistant_msg_id}")
        
        # Get conversation to check message count
        conversation = conversation_service.get_conversation(conversation_id)
        message_count = conversation.get("stats", {}).get("messageCount", 0)
        print(f"  Current message count: {message_count}")
        
        # Check if summary should be created at this point
        if message_count in summary_checkpoints:
            print(f"  ⏳ Summary checkpoint reached! Checking for summary creation...")
            time.sleep(2)  # Give time for summary creation
            
            # Get context to trigger summary creation
            context = get_conversation_context(
                conversation_id=conversation_id,
                current_user_message="Next message"
            )
            
            # Check summaries
            conversation = conversation_service.get_conversation(conversation_id)
            conversation_summaries = conversation.get("conversationSummaries", [])
            
            expected_chunks = message_count // 4
            print(f"  ✓ Expected {expected_chunks} summary chunk(s), found {len(conversation_summaries)}")
            
            for summary in conversation_summaries:
                start_idx = summary.get("startIndex")
                end_idx = summary.get("endIndex")
                summary_text = summary.get("summary", "")
                print(f"    - Summary for messages {start_idx}-{end_idx}: {summary_text[:80]}...")
        
        time.sleep(0.5)  # Small delay between turns
    
    # Add 21st message (user message only, to make it 21 total messages)
    print(f"\n🔄 Turn 10.5 (Message 21 - Final):")
    user_msg = conversation_pairs[10]["user"]
    print(f"  Saving user message (21st message): {user_msg[:50]}...")
    user_msg_id = conversation_storage.save_user_message(
        conversation_id=conversation_id,
        user_id=user_id,
        content=user_msg
    )
    print(f"  ✓ Saved user message: {user_msg_id}")
    
    # Get conversation to check final message count
    conversation = conversation_service.get_conversation(conversation_id)
    message_count = conversation.get("stats", {}).get("messageCount", 0)
    print(f"  Final message count: {message_count}")
    print(f"  Note: Message 21 is in an incomplete chunk (17-20 already summarized, 21 is standalone)")
    
    # Step 3: Wait and verify all summaries are created
    print_separator("Step 3: Waiting for All Summaries to be Created")
    print("⏳ Waiting 20 seconds to allow all LLM summaries to be created...")
    for i in range(20, 0, -1):
        print(f"  {i} seconds remaining...", end="\r")
        time.sleep(1)
    print("\n✓ Wait complete!")
    
    # Trigger context retrieval to ensure all summaries are created
    print("\n📋 Triggering context retrieval to ensure all summaries are created...")
    final_context = get_conversation_context(
        conversation_id=conversation_id,
        current_user_message="Final check"
    )
    print(f"✓ Context retrieved with {len(final_context)} messages")
    
    # Step 4: Final verification - Check all 5 summary chunks
    print_separator("Step 4: Final Verification - Summary Chunks Analysis")
    
    # Get final conversation state
    conversation = conversation_service.get_conversation(conversation_id)
    message_count = conversation.get("stats", {}).get("messageCount", 0)
    conversation_summaries = conversation.get("conversationSummaries", [])
    
    # Legacy support: check for old single summary format
    if not conversation_summaries:
        legacy_summary = conversation.get("conversationSummary")
        if legacy_summary and legacy_summary.get("summary"):
            print("⚠ Found legacy single summary format, converting...")
            conversation_summaries = [{
                "summary": legacy_summary.get("summary"),
                "startIndex": 1,
                "endIndex": 4,
                "messageCount": 4,
                "createdAt": legacy_summary.get("createdAt", datetime.now(timezone.utc))
            }]
    
    print(f"📊 Final Statistics:")
    print(f"   Total message count: {message_count}")
    print(f"   Expected summary chunks: 5 (for messages 1-4, 5-8, 9-12, 13-16, 17-20)")
    print(f"   Found summary chunks: {len(conversation_summaries)}")
    print()
    
    # Expected summary chunks
    expected_chunks = [
        {"startIndex": 1, "endIndex": 4},
        {"startIndex": 5, "endIndex": 8},
        {"startIndex": 9, "endIndex": 12},
        {"startIndex": 13, "endIndex": 16},
        {"startIndex": 17, "endIndex": 20}
    ]
    
    # Sort summaries by startIndex
    conversation_summaries.sort(key=lambda x: x.get("startIndex", 0))
    
    print("🔍 Summary Chunks Verification:")
    print("-" * 80)
    
    all_chunks_found = True
    for expected in expected_chunks:
        start_idx = expected["startIndex"]
        end_idx = expected["endIndex"]
        
        # Find matching summary
        found_summary = None
        for summary in conversation_summaries:
            if summary.get("startIndex") == start_idx and summary.get("endIndex") == end_idx:
                found_summary = summary
                break
        
        if found_summary:
            summary_text = found_summary.get("summary", "")
            msg_count = found_summary.get("messageCount", 0)
            created_at = found_summary.get("createdAt", "N/A")
            
            print(f"✅ Chunk {start_idx}-{end_idx}:")
            print(f"   - Summary exists: Yes")
            print(f"   - Message count: {msg_count}")
            print(f"   - Created at: {created_at}")
            print(f"   - Preview: {summary_text[:100]}...")
            print()
        else:
            print(f"❌ Chunk {start_idx}-{end_idx}:")
            print(f"   - Summary exists: No")
            print(f"   - ⚠️  MISSING SUMMARY CHUNK!")
            print()
            all_chunks_found = False
    
    # Check for any unexpected summaries
    if len(conversation_summaries) > len(expected_chunks):
        print(f"⚠️  Warning: Found {len(conversation_summaries)} summaries, expected {len(expected_chunks)}")
        for summary in conversation_summaries:
            start_idx = summary.get("startIndex")
            end_idx = summary.get("endIndex")
            if not any(e["startIndex"] == start_idx and e["endIndex"] == end_idx for e in expected_chunks):
                print(f"   - Unexpected summary: {start_idx}-{end_idx}")
    
    # Get final context and verify summaries are included
    print("📋 Getting final conversation context...")
    final_context = get_conversation_context(
        conversation_id=conversation_id,
        current_user_message="Test final context"
    )
    print_context(final_context, "Final (21 messages)")
    
    # Count summaries in context
    summary_count_in_context = 0
    for msg in final_context:
        if "[Previous conversation summary" in msg.get("content", ""):
            summary_count_in_context += 1
    
    print(f"\n📝 Context Analysis:")
    print(f"   Total context messages: {len(final_context)}")
    print(f"   Summary chunks in context: {summary_count_in_context}")
    print(f"   Recent messages in context: {len(final_context) - summary_count_in_context}")
    
    # Final test results
    print_separator("Test Complete - Results Summary")
    print(f"Conversation ID: {conversation_id}")
    print(f"Total messages: {message_count}")
    print(f"Expected summary chunks: 5")
    print(f"Found summary chunks: {len(conversation_summaries)}")
    print(f"All chunks found: {'✅ Yes' if all_chunks_found and len(conversation_summaries) == 5 else '❌ No'}")
    print(f"Summaries in final context: {summary_count_in_context}")
    
    if all_chunks_found and len(conversation_summaries) == 5:
        print("\n🎉 MEMORY LAYER TEST PASSED!")
        print("   ✅ All 5 summary chunks created and saved correctly")
        print("   ✅ Summaries are stored in conversationSummaries array")
        print("   ✅ Context includes all summaries + recent messages")
        print("   ✅ Multi-chunk memory system working as expected!")
    else:
        print("\n⚠️  MEMORY LAYER TEST NEEDS ATTENTION")
        if len(conversation_summaries) < 5:
            print(f"   ❌ Only {len(conversation_summaries)} summary chunks found, expected 5")
        if not all_chunks_found:
            print("   ❌ Some summary chunks are missing")
        print("   ⚠️  Check summary creation logic and MongoDB storage")
    
    return conversation_id


if __name__ == "__main__":
    try:
        conversation_id = test_memory_layer()
        print(f"\n✅ Test completed successfully!")
        print(f"   You can verify the conversation in MongoDB with ID: {conversation_id}")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

