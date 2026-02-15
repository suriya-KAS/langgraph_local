#!/usr/bin/env python3
"""
Test script to verify MongoDB integration with API.
This simulates what happens when a cURL request is made.
"""

import requests
import json
import secrets
from datetime import datetime

# API endpoint
API_URL = "http://localhost:8502/api/chat/message"

# Generate test IDs
conversation_id = f"conv_{secrets.token_hex(8)}"
user_id = "user_test_user_123"

# Test request payload
test_payload = {
    "message": "Hello, I want to create a listing for my product",
    "conversationId": conversation_id,
    "messageType": "text",
    "context": {
        "userId": user_id,
        "clientInfo": {
            "device": "desktop",
            "appVersion": "1.0.0",
            "timezone": "Asia/Kolkata",
            "platform": "web",
            "country": "IN"
        }
    },
    "language": "English"
}

print("=" * 60)
print("Testing MongoDB Integration with API")
print("=" * 60)
print(f"\nConversation ID: {conversation_id}")
print(f"User ID: {user_id}")
print(f"\nSending request to: {API_URL}")
print(f"Message: {test_payload['message']}")
print("\n" + "-" * 60)

try:
    # Make the request
    response = requests.post(API_URL, json=test_payload, timeout=30)
    
    print(f"\nResponse Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Success: {data.get('success', False)}")
        
        if data.get('success'):
            message_data = data.get('data', {})
            print(f"\n✓ API Response received:")
            print(f"  Message ID: {message_data.get('messageId')}")
            print(f"  Intent: {message_data.get('intent')}")
            print(f"  Reply: {message_data.get('reply', '')[:100]}...")
            print(f"  Wallet Balance: {message_data.get('walletBalance')}")
            
            print("\n" + "-" * 60)
            print("✓ Request completed successfully!")
            print("\nNow check MongoDB to verify:")
            print(f"  1. User message was saved (conversationId: {conversation_id})")
            print(f"  2. Assistant message was saved (conversationId: {conversation_id})")
            print("\nYou can verify with:")
            print(f"  - MongoDB Compass or mongo shell")
            print(f"  - Query: db.messages.find({{conversationId: '{conversation_id}'}})")
        else:
            error = data.get('error', {})
            print(f"\n✗ API Error:")
            print(f"  Code: {error.get('code')}")
            print(f"  Message: {error.get('message')}")
    else:
        print(f"\n✗ HTTP Error: {response.status_code}")
        print(f"Response: {response.text}")
        
except requests.exceptions.ConnectionError:
    print("\n✗ Connection Error: Could not connect to API")
    print("Make sure the API server is running on http://localhost:8502")
    print("\nTo start the server:")
    print("  cd /Users/suriya/Documents/KAS/chatbot/PROTOTYPE")
    print("  python -m uvicorn src.api.routes:app --reload")
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)


