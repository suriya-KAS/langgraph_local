"""
Test that AWS credentials from .env are loaded and valid.
Uses STS GetCallerIdentity to verify access without exposing secrets.
"""
import os
import sys
from pathlib import Path

# Load .env from project root
project_root = Path(__file__).resolve().parent
env_file = project_root / ".env"

if not env_file.exists():
    print(f"ERROR: .env not found at {env_file}")
    sys.exit(1)

from dotenv import load_dotenv
load_dotenv(env_file)

# Check env vars are set (don't print values)
access_key = os.getenv("AWS_ACCESS_KEY_ID")
secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
region = os.getenv("AWS_DEFAULT_REGION")

missing = []
if not access_key or access_key.strip() == "":
    missing.append("AWS_ACCESS_KEY_ID")
if not secret_key or secret_key.strip() == "":
    missing.append("AWS_SECRET_ACCESS_KEY")
if not region or region.strip() == "":
    missing.append("AWS_DEFAULT_REGION")

if missing:
    print(f"FAIL: Missing or empty in .env: {', '.join(missing)}")
    sys.exit(1)

print("OK: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION are set")
print(f"    Region: {region}")

# Verify credentials with AWS
try:
    import boto3
    sts = boto3.client("sts", region_name=region)
    identity = sts.get_caller_identity()
    print("OK: AWS credentials are valid")
    print(f"    Account: {identity['Account']}")
    print(f"    User ARN: {identity['Arn']}")
except Exception as e:
    print(f"FAIL: Could not authenticate with AWS: {e}")
    sys.exit(1)

# --- Knowledge Base retrieve test ---
kb_id = os.getenv("KNOWLEDGE_BASE_ID") or os.getenv("BEDROCK_KNOWLEDGE_BASE_ID")
if not kb_id or kb_id.strip() == "":
    print("\nSKIP: KNOWLEDGE_BASE_ID (or BEDROCK_KNOWLEDGE_BASE_ID) not set in .env")
else:
    print(f"\nTesting Knowledge Base retrieve (ID: {kb_id})...")
    try:
        from langchain_aws import AmazonKnowledgeBasesRetriever
        retriever = AmazonKnowledgeBasesRetriever(
            knowledge_base_id=kb_id.strip(),
            retrieval_config={
                "vectorSearchConfiguration": {
                    "numberOfResults": 5,
                }
            },
        )
        test_query = "What is MySellerCentral?"
        docs = retriever.invoke(test_query)
        if docs:
            print(f"OK: KB retrieve succeeded. Got {len(docs)} document(s).")
            if docs[0].page_content:
                snippet = (docs[0].page_content[:200] + "…") if len(docs[0].page_content) > 200 else docs[0].page_content
                print(f"    First doc snippet: {snippet}")
        else:
            print("OK: KB retrieve succeeded but returned no documents (empty KB or no match).")
    except Exception as e:
        print(f"FAIL: KB retrieve error: {e}")
        sys.exit(1)

print("\nAll checks passed. AWS credentials and Knowledge Base retrieve are OK.")
