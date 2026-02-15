"""
Test script for Memory Management Layer

This script tests the memory management functionality:
- Initial summary generation at turn 4
- Incremental summary generation every 5 messages
- Summary storage and retrieval from MongoDB
- Integration with conversation service
"""
import os
import sys
import asyncio
from datetime import datetime, timezone

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger_config import get_logger
from src.core.memory_layer import get_memory_layer, INITIAL_SUMMARY_THRESHOLD, INCREMENTAL_SUMMARY_INTERVAL
from database.conversation_storage import get_conversation_storage
from src.database.conversation_service import get_conversation_service

logger = get_logger(__name__)


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_test_header(test_name: str):
    """Print formatted test header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}TEST: {test_name}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}\n")


def print_success(message: str):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {message}{Colors.END}")


def print_error(message: str):
    """Print error message"""
    print(f"{Colors.RED}✗ {message}{Colors.END}")


def print_info(message: str):
    """Print info message"""
    print(f"{Colors.YELLOW}ℹ {message}{Colors.END}")


def create_test_conversation(user_id: str = "user_test_memory") -> str:
    """Create a test conversation"""
    conversation_storage = get_conversation_storage()
    conversation_id = conversation_storage.get_or_create_conversation(
        user_id=user_id,
        conversation_id=None,
        client_info={
            "device": "desktop",
            "appVersion": "1.0.0",
            "timezone": "Asia/Kolkata"
        }
    )
    return conversation_id


def add_test_messages(conversation_id: str, user_id: str, num_turns: int):
    """Add test messages to simulate a conversation"""
    conversation_storage = get_conversation_storage()
    messages = []
    
    # Sample conversation messages
    user_messages = [
        "Hello! I'm interested in learning about MySellerCentral.",
        "What agents do you offer?",
        "Tell me about the Smart Listing Agent.",
        "How much does it cost?",
        "What marketplaces does it support?",
        "Can it work with Amazon?",
        "How about Walmart?",
        "What are the key features?",
        "Can it generate product descriptions?",
        "Does it support multiple languages?",
        "What about image optimization?",
        "Tell me about pricing plans.",
        "What's included in the Silver plan?",
        "How does the trial work?",
        "Can I cancel anytime?",
    ]
    
    assistant_messages = [
        "Hello! I'd be happy to help you learn about MySellerCentral. We're a comprehensive e-commerce management platform with AI-powered agents to help sellers grow their business.",
        "We offer several AI agents: Smart Listing Agent, Text Grading Enhancement, Image Grading Enhancement, Banner Image Generator, Lifestyle Image Generator, and more. Each agent serves a specific purpose in your e-commerce workflow.",
        "The Smart Listing Agent helps you create optimized product listings. It generates compelling product titles, descriptions, and keywords that improve your search rankings and conversion rates.",
        "The Smart Listing Agent costs 50 tokens per listing. Tokens can be purchased via Razorpay (India) or Stripe (International) and are valid for 6 months.",
        "The Smart Listing Agent supports multiple marketplaces including Amazon, Walmart, Shopify, and ONDC.",
        "Yes! The Smart Listing Agent works seamlessly with Amazon. It's optimized for Amazon's requirements and guidelines.",
        "Absolutely! Walmart is one of our supported marketplaces. The agent will create listings that meet Walmart's specifications.",
        "Key features include: automated title generation, SEO-optimized descriptions, keyword suggestions, bulk listing creation, and marketplace-specific optimization.",
        "Yes, the Smart Listing Agent can generate detailed product descriptions based on your product specifications and target marketplace.",
        "Currently, the Smart Listing Agent supports English. Multi-language support is coming in future updates.",
        "Image optimization is handled by our Image Grading Enhancement agent, which is separate from the Smart Listing Agent.",
        "We offer several pricing plans: BASIC (for new sellers), BRONZE (for growing businesses), SILVER (with analytics), GOLD (for high volume), and PLATINUM (enterprise). Silver, Gold, and Platinum plans include a 30-day free trial.",
        "The Silver plan includes advanced analytics, priority support, bulk operations, and access to premium agents. It's perfect for sellers who want deeper insights into their performance.",
        "The 30-day trial gives you full access to all Silver plan features. No credit card required to start. You can upgrade, downgrade, or cancel anytime during or after the trial.",
        "Yes, you can cancel your subscription at any time. There are no long-term contracts or cancellation fees.",
    ]
    
    print_info(f"Adding {num_turns} turns (user + assistant pairs) to conversation...")
    
    for i in range(min(num_turns, len(user_messages))):
        # Add user message
        user_msg_id = conversation_storage.save_user_message(
            conversation_id=conversation_id,
            user_id=user_id,
            content=user_messages[i],
            message_type="text"
        )
        messages.append({"role": "user", "content": user_messages[i], "id": user_msg_id})
        
        # Add assistant message
        assistant_msg_id = conversation_storage.save_assistant_message(
            conversation_id=conversation_id,
            user_id=user_id,
            content=assistant_messages[i],
            intent="general_query"
        )
        messages.append({"role": "assistant", "content": assistant_messages[i], "id": assistant_msg_id})
        
        print_info(f"  Added turn {i+1}: User message + Assistant response")
    
    return messages


def test_memory_layer_initialization():
    """Test that memory layer initializes correctly"""
    print_test_header("Memory Layer Initialization")
    
    try:
        memory_layer = get_memory_layer()
        assert memory_layer is not None, "Memory layer should not be None"
        assert memory_layer.conversation_service is not None, "Conversation service should be initialized"
        assert memory_layer.conversation_storage is not None, "Conversation storage should be initialized"
        print_success("Memory layer initialized successfully")
        return True
    except Exception as e:
        print_error(f"Memory layer initialization failed: {e}")
        return False


def test_turns_1_3_raw_messages_only():
    """Test that turns 1-3 return raw messages only (no summary)"""
    print_test_header("Turns 1-3: Raw Messages Only")
    
    try:
        # Create test conversation
        user_id = "user_test_raw"
        conversation_id = create_test_conversation(user_id)
        print_info(f"Created test conversation: {conversation_id}")
        
        # Add 3 turns (6 messages total: 3 user + 3 assistant)
        messages = add_test_messages(conversation_id, user_id, 3)
        
        # Get formatted chat history
        memory_layer = get_memory_layer()
        chat_history = memory_layer.get_formatted_chat_history_for_backend(conversation_id)
        
        # Verify no summary exists yet
        conversation_service = get_conversation_service()
        conversation = conversation_service.get_conversation(conversation_id)
        summary = conversation.get("conversationSummary") if conversation else None
        
        assert summary is None, "No summary should exist before turn 4"
        print_success("No summary exists before turn 4 (as expected)")
        
        # Verify raw messages are returned
        # Should have 6 messages (3 user + 3 assistant), no summary message
        assert len(chat_history) == 6, f"Expected 6 raw messages, got {len(chat_history)}"
        print_success(f"Returned {len(chat_history)} raw messages (no summary)")
        
        # Verify message structure
        for msg in chat_history:
            assert "role" in msg, "Message should have 'role' key"
            assert "content" in msg, "Message should have 'content' key"
            assert msg["role"] in ["user", "assistant"], f"Invalid role: {msg['role']}"
        
        print_success("Message structure is correct")
        return True
        
    except Exception as e:
        print_error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_initial_summary_at_turn_4():
    """Test that initial summary is generated at turn 4"""
    print_test_header("Turn 4: Initial Summary Generation")
    
    try:
        # Create test conversation
        user_id = "user_test_initial_summary"
        conversation_id = create_test_conversation(user_id)
        print_info(f"Created test conversation: {conversation_id}")
        
        # Add 4 turns (8 messages total)
        messages = add_test_messages(conversation_id, user_id, 4)
        
        # Trigger memory layer to process (this will generate summary)
        memory_layer = get_memory_layer()
        chat_history = memory_layer.get_formatted_chat_history_for_backend(conversation_id)
        
        # Verify summary was created
        conversation_service = get_conversation_service()
        conversation = conversation_service.get_conversation(conversation_id)
        summary = conversation.get("conversationSummary") if conversation else None
        
        assert summary is not None, "Summary should exist after turn 4"
        assert "content" in summary, "Summary should have 'content' field"
        assert "messageCount" in summary, "Summary should have 'messageCount' field"
        assert summary["messageCount"] == 6, f"Expected 6 messages summarized (first 3 turns), got {summary['messageCount']}"
        
        print_success(f"Summary generated successfully (summarized {summary['messageCount']} messages)")
        print_info(f"Summary content (first 200 chars): {summary['content'][:200]}...")
        
        # Verify chat history includes summary
        # Should have: 1 summary message + 2 recent messages (turn 4)
        assert len(chat_history) >= 3, f"Expected at least 3 messages (summary + turn 4), got {len(chat_history)}"
        
        # First message should be the summary context
        first_msg = chat_history[0]
        assert first_msg["role"] == "user", "First message should be summary context (user role)"
        assert "[Previous conversation summary" in first_msg["content"], "First message should contain summary"
        
        print_success("Summary included in chat history correctly")
        return True
        
    except Exception as e:
        print_error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_incremental_summary_every_5_messages():
    """Test that incremental summaries are generated every 5 messages"""
    print_test_header("Incremental Summary Generation (Every 5 Messages)")
    
    try:
        # Create test conversation
        user_id = "user_test_incremental"
        conversation_id = create_test_conversation(user_id)
        print_info(f"Created test conversation: {conversation_id}")
        
        # Add 10 turns (20 messages total)
        # This should trigger:
        # - Initial summary at turn 4 (summarizes first 6 messages)
        # - Incremental summary at turn 9 (summarizes messages 7-16, then merges)
        messages = add_test_messages(conversation_id, user_id, 10)
        
        # Trigger memory layer to process
        memory_layer = get_memory_layer()
        chat_history = memory_layer.get_formatted_chat_history_for_backend(conversation_id)
        
        # Verify summary exists and was updated
        conversation_service = get_conversation_service()
        conversation = conversation_service.get_conversation(conversation_id)
        summary = conversation.get("conversationSummary") if conversation else None
        
        assert summary is not None, "Summary should exist"
        print_info(f"Summary messageCount: {summary['messageCount']}")
        print_info(f"Total messages: {len(messages)}")
        
        # After 10 turns (20 messages), we should have:
        # - Initial summary at turn 4 (6 messages)
        # - Incremental at turn 9 (should summarize up to message 16, then merge)
        # So final summary should cover many messages
        assert summary["messageCount"] > 6, "Summary should have been updated with more messages"
        
        print_success(f"Incremental summary generated (summarized {summary['messageCount']} messages)")
        print_info(f"Summary content (first 300 chars): {summary['content'][:300]}...")
        
        # Verify chat history includes summary and recent messages
        assert len(chat_history) > 0, "Chat history should not be empty"
        assert chat_history[0]["role"] == "user", "First message should be summary context"
        
        print_success("Incremental summary working correctly")
        return True
        
    except Exception as e:
        print_error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_summary_retrieval_accuracy():
    """Test that summaries accurately represent conversation content"""
    print_test_header("Summary Retrieval and Accuracy")
    
    try:
        # Create test conversation with specific topics
        user_id = "user_test_accuracy"
        conversation_id = create_test_conversation(user_id)
        print_info(f"Created test conversation: {conversation_id}")
        
        # Add specific messages about a topic
        conversation_storage = get_conversation_storage()
        
        # Turn 1: Greeting
        conversation_storage.save_user_message(conversation_id, user_id, "Hello!")
        conversation_storage.save_assistant_message(
            conversation_id, user_id, "Hi! How can I help?", "general_query"
        )
        
        # Turn 2: Ask about Smart Listing Agent
        conversation_storage.save_user_message(conversation_id, user_id, "Tell me about Smart Listing Agent")
        conversation_storage.save_assistant_message(
            conversation_id, user_id, 
            "Smart Listing Agent creates optimized product listings for Amazon, Walmart, and other marketplaces. It costs 50 tokens per listing.",
            "general_query"
        )
        
        # Turn 3: Ask about pricing
        conversation_storage.save_user_message(conversation_id, user_id, "How much does it cost?")
        conversation_storage.save_assistant_message(
            conversation_id, user_id,
            "It costs 50 tokens per listing. Tokens can be purchased via Razorpay or Stripe.",
            "general_query"
        )
        
        # Turn 4: Ask about marketplaces (this should trigger summary)
        conversation_storage.save_user_message(conversation_id, user_id, "What marketplaces are supported?")
        conversation_storage.save_assistant_message(
            conversation_id, user_id,
            "The Smart Listing Agent supports Amazon, Walmart, Shopify, and ONDC.",
            "general_query"
        )
        
        # Get formatted chat history (this will generate summary)
        memory_layer = get_memory_layer()
        chat_history = memory_layer.get_formatted_chat_history_for_backend(conversation_id)
        
        # Verify summary was created
        conversation_service = get_conversation_service()
        conversation = conversation_service.get_conversation(conversation_id)
        summary = conversation.get("conversationSummary") if conversation else None
        
        assert summary is not None, "Summary should exist"
        summary_content = summary["content"].lower()
        
        # Verify summary contains key topics
        key_topics = ["smart listing", "agent", "tokens", "marketplace", "cost"]
        found_topics = [topic for topic in key_topics if topic in summary_content]
        
        print_info(f"Summary contains {len(found_topics)}/{len(key_topics)} key topics: {found_topics}")
        assert len(found_topics) >= 3, f"Summary should contain at least 3 key topics, found: {found_topics}"
        
        print_success("Summary accurately represents conversation content")
        return True
        
    except Exception as e:
        print_error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_empty_conversation():
    """Test memory layer with empty conversation"""
    print_test_header("Empty Conversation Handling")
    
    try:
        user_id = "user_test_empty"
        conversation_id = create_test_conversation(user_id)
        print_info(f"Created test conversation: {conversation_id}")
        
        memory_layer = get_memory_layer()
        chat_history = memory_layer.get_formatted_chat_history_for_backend(conversation_id)
        
        # Should return empty list
        assert isinstance(chat_history, list), "Should return a list"
        assert len(chat_history) == 0, "Empty conversation should return empty list"
        
        print_success("Empty conversation handled correctly")
        return True
        
    except Exception as e:
        print_error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_test_conversations():
    """Clean up test conversations"""
    print_info("\nCleaning up test conversations...")
    conversation_service = get_conversation_service()
    
    test_user_ids = [
        "user_test_memory",
        "user_test_raw",
        "user_test_initial_summary",
        "user_test_incremental",
        "user_test_accuracy",
        "user_test_empty"
    ]
    
    cleaned = 0
    for user_id in test_user_ids:
        conversations = conversation_service.get_user_conversations(user_id, limit=100)
        for conv in conversations:
            conversation_service.delete_conversation(conv["_id"], hard_delete=True)
            cleaned += 1
    
    print_info(f"Cleaned up {cleaned} test conversations")


def run_all_tests():
    """Run all test cases"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}MEMORY LAYER TEST SUITE{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}\n")
    
    tests = [
        ("Memory Layer Initialization", test_memory_layer_initialization),
        ("Empty Conversation", test_empty_conversation),
        ("Turns 1-3: Raw Messages Only", test_turns_1_3_raw_messages_only),
        ("Turn 4: Initial Summary Generation", test_initial_summary_at_turn_4),
        ("Incremental Summary Generation", test_incremental_summary_every_5_messages),
        ("Summary Retrieval Accuracy", test_summary_retrieval_accuracy),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print_error(f"Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Print summary
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}TEST SUMMARY{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        if result:
            print_success(f"{test_name}: PASSED")
        else:
            print_error(f"{test_name}: FAILED")
    
    print(f"\n{Colors.BOLD}Results: {passed}/{total} tests passed{Colors.END}\n")
    
    # Cleanup
    try:
        cleanup_test_conversations()
    except Exception as e:
        print_error(f"Cleanup failed: {e}")
    
    return passed == total


if __name__ == "__main__":
    import sys
    
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Tests interrupted by user{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Test suite crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)