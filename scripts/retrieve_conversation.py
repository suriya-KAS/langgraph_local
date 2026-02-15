#!/usr/bin/env python3
"""
Script to retrieve all messages for a conversation ID from MongoDB.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
import sys
from typing import Any

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retrieve MongoDB messages for a conversation.")
    parser.add_argument(
        "conversation_id",
        nargs="?",
        default=os.getenv("CONVERSATION_ID"),
        help="Conversation ID (or set CONVERSATION_ID).",
    )
    parser.add_argument(
        "--database",
        default=os.getenv("MONGODB_DATABASE", "msc-chatbot"),
        help="MongoDB database name (default: MONGODB_DATABASE or 'msc-chatbot').",
    )
    parser.add_argument(
        "--collection",
        default=os.getenv("MONGODB_MESSAGES_COLLECTION", "messages"),
        help="MongoDB collection name (default: MONGODB_MESSAGES_COLLECTION or 'messages').",
    )
    return parser.parse_args(argv)


def retrieve_conversation(*, conversation_id: str, database_name: str, collection_name: str) -> int:
    """Retrieve all messages for a conversation ID."""
    mongo_uri = _get_required_env("MONGODB_URI")
    client: MongoClient | None = None
    try:
        # Connect to MongoDB
        print("Connecting to MongoDB...")
        client = MongoClient(mongo_uri)
        db = client[database_name]
        collection = db[collection_name]
        
        # Test connection
        client.admin.command("ping")
        print(f"✓ Successfully connected to MongoDB database: {database_name}\n")
        
        # Query messages for the conversation
        print(f"Searching for messages with conversationId: {conversation_id}")
        print("=" * 80)
        
        messages = list(
            collection.find({"conversationId": conversation_id})
            .sort("timestamp", 1)  # Sort by timestamp ascending (oldest first)
        )
        
        if not messages:
            print(f"\n⚠ No messages found for conversationId: {conversation_id}")
            print("\nPossible reasons:")
            print("  1. The conversation ID doesn't exist in the database")
            print("  2. The conversation ID format is incorrect")
            print("  3. No messages have been stored for this conversation yet")
            return 2
        
        print(f"\n✓ Found {len(messages)} message(s)\n")
        print("=" * 80)
        
        # Display each message
        for idx, msg in enumerate(messages, 1):
            print(f"\n📨 Message #{idx}")
            print("-" * 80)
            print(f"Message ID:     {msg.get('_id', 'N/A')}")
            print(f"Role:          {msg.get('role', 'N/A').upper()}")
            print(f"Conversation:  {msg.get('conversationId', 'N/A')}")
            print(f"User ID:       {msg.get('userId', 'N/A')}")
            print(f"Message Type:  {msg.get('messageType', 'N/A')}")
            print(f"Timestamp:     {msg.get('timestamp', 'N/A')}")
            print(f"Created At:    {msg.get('createdAt', 'N/A')}")
            
            # Content
            content = msg.get('content', '')
            if content:
                print(f"\nContent:")
                print(f"  {content[:200]}{'...' if len(content) > 200 else ''}")
            
            # User request data
            if msg.get('userRequest'):
                print(f"\nUser Request Data:")
                user_req = msg.get('userRequest', {})
                if isinstance(user_req, dict):
                    for key, value in user_req.items():
                        if isinstance(value, dict):
                            print(f"  {key}:")
                            for k, v in value.items():
                                print(f"    {k}: {v}")
                        else:
                            print(f"  {key}: {value}")
            
            # Assistant response data
            if msg.get('assistantResponse'):
                print(f"\nAssistant Response Data:")
                asst_resp = msg.get('assistantResponse', {})
                if isinstance(asst_resp, dict):
                    for key, value in asst_resp.items():
                        print(f"  {key}: {value}")
            
            # Agent card
            if msg.get('agentCard'):
                print(f"\nAgent Card:")
                agent_card = msg.get('agentCard', {})
                if isinstance(agent_card, dict):
                    for key, value in agent_card.items():
                        print(f"  {key}: {value}")
            
            # Suggested agents
            if msg.get('suggestedAgents'):
                print(f"\nSuggested Agents ({len(msg.get('suggestedAgents', []))}):")
                for agent in msg.get('suggestedAgents', []):
                    if isinstance(agent, dict):
                        print(f"  - {agent.get('agentName', 'N/A')} ({agent.get('agentId', 'N/A')})")
            
            # Quick actions
            if msg.get('quickActions'):
                print(f"\nQuick Actions ({len(msg.get('quickActions', []))}):")
                for action in msg.get('quickActions', []):
                    if isinstance(action, dict):
                        print(f"  - {action.get('label', 'N/A')} ({action.get('action', 'N/A')})")
            
            # Processing metadata
            if msg.get('processing'):
                print(f"\nProcessing Metadata:")
                processing = msg.get('processing', {})
                if isinstance(processing, dict):
                    for key, value in processing.items():
                        print(f"  {key}: {value}")
            
            # Error (if any)
            if msg.get('error'):
                print(f"\n⚠ Error:")
                error = msg.get('error', {})
                if isinstance(error, dict):
                    for key, value in error.items():
                        print(f"  {key}: {value}")
            
            print()
        
        # Summary
        print("=" * 80)
        print("\n📊 Summary:")
        user_messages = [m for m in messages if m.get('role') == 'user']
        assistant_messages = [m for m in messages if m.get('role') == 'assistant']
        system_messages = [m for m in messages if m.get('role') == 'system']
        
        print(f"  Total Messages:     {len(messages)}")
        print(f"  User Messages:      {len(user_messages)}")
        print(f"  Assistant Messages: {len(assistant_messages)}")
        print(f"  System Messages:    {len(system_messages)}")
        
        if messages:
            first_msg = messages[0]
            last_msg = messages[-1]
            print(f"\n  First Message:       {first_msg.get('timestamp', 'N/A')}")
            print(f"  Last Message:        {last_msg.get('timestamp', 'N/A')}")
        
        print("\n" + "=" * 80)
        
        # Option to export to JSON (skip if not in interactive terminal)
        try:
            export = input("\nExport to JSON file? (y/n): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            # Not in interactive terminal, skip export
            export = 'n'
        
        if export == 'y':
            filename = f"conversation_{conversation_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            # Convert ObjectId and datetime to strings for JSON serialization
            export_data: list[dict[str, Any]] = []
            for msg in messages:
                msg_dict: dict[str, Any] = {}
                for key, value in msg.items():
                    if isinstance(value, datetime):
                        msg_dict[key] = value.isoformat()
                    else:
                        msg_dict[key] = value
                export_data.append(msg_dict)
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
            print(f"✓ Exported to: {filename}")

        return 0
    except Exception as e:
        print(f"✗ Error: {e}")
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    args = _parse_args(sys.argv[1:])
    if not args.conversation_id:
        raise SystemExit(
            "Missing conversation_id. Provide it as an argument or set CONVERSATION_ID."
        )

    print("=" * 80)
    print("MongoDB Conversation Retriever")
    print("=" * 80)
    print()

    raise SystemExit(
        retrieve_conversation(
            conversation_id=args.conversation_id,
            database_name=args.database,
            collection_name=args.collection,
        )
    )

