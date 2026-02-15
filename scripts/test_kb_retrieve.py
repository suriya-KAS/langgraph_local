#!/usr/bin/env python3
"""
Quick test: retrieve content from AWS Bedrock Knowledge Base (ID: 6CKNJD5JXX).
Run from project root: python scripts/test_kb_retrieve.py
"""
import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv()

# Optional: force KB ID for this test
KB_ID = os.getenv("KNOWLEDGE_BASE_ID") or "6CKNJD5JXX"
REGION = os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION") or "us-east-1"


def main():
    print(f"Testing KB retrieval from AWS Bedrock")
    print(f"  KNOWLEDGE_BASE_ID: {KB_ID}")
    print(f"  Region: {REGION}")
    print()

    if not os.getenv("AWS_ACCESS_KEY_ID") or not os.getenv("AWS_SECRET_ACCESS_KEY"):
        print("ERROR: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set (.env or env)")
        return 1

    try:
        from langchain_aws import AmazonKnowledgeBasesRetriever
    except ImportError as e:
        print(f"ERROR: langchain_aws not installed: {e}")
        return 1

    retriever = AmazonKnowledgeBasesRetriever(
        knowledge_base_id=KB_ID,
        retrieval_config={
            "vectorSearchConfiguration": {"numberOfResults": 5},
        },
    )

    test_query = "What is MySellerCentral?"
    print(f"Query: \"{test_query}\"")
    try:
        docs = retriever.invoke(test_query)
        n = len(docs)
        print(f"SUCCESS: Retrieved {n} document(s) from KB {KB_ID}")
        if n > 0:
            print(f"First result (length): {len(docs[0].page_content)} chars")
            print("Preview:", (docs[0].page_content[:200] + "..." if len(docs[0].page_content) > 200 else docs[0].page_content))
        return 0
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
