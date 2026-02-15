#!/usr/bin/env python3
"""
Extract all content from AWS Bedrock Knowledge Base and save to markdown file
Run: python scripts/extract_knowledge_base.py
"""
import os
import sys
import boto3
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger_config import get_logger

# Initialize logger
logger = get_logger(__name__)

# Load environment variables from .env file (for local development)
# boto3 automatically picks up AWS credentials from environment variables or IAM roles
load_dotenv()

# Import KB utility
from utils.kb_utils import get_knowledge_base_id

REGION = os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION") or "us-east-1"

def extract_knowledge_base_content():
    """Extract all content from the knowledge base"""
    try:
        # Get Knowledge Base ID from environment
        KNOWLEDGE_BASE_ID = get_knowledge_base_id()
        logger.info(f"Connecting to AWS Bedrock Knowledge Base: {KNOWLEDGE_BASE_ID}")
        
        # Initialize Bedrock Agent Runtime client for querying
        bedrock_agent = boto3.client('bedrock-agent-runtime', region_name=REGION)
        
        # Initialize Bedrock Agent client for metadata
        bedrock_agent_client = boto3.client('bedrock-agent', region_name=REGION)
        
        # Get knowledge base details
        try:
            kb_info = bedrock_agent_client.get_knowledge_base(knowledgeBaseId=KNOWLEDGE_BASE_ID)
            logger.info(f"Knowledge Base Name: {kb_info.get('knowledgeBase', {}).get('name', 'Unknown')}")
        except Exception as e:
            logger.warning(f"Could not get KB info: {e}")
        
        # Use the retriever approach - query with broad terms to get all documents
        from langchain_aws import AmazonKnowledgeBasesRetriever
        
        retriever = AmazonKnowledgeBasesRetriever(
            knowledge_base_id=KNOWLEDGE_BASE_ID,
            retrieval_config={
                "vectorSearchConfiguration": {
                    "numberOfResults": 20,  # Maximum results per query
                }
            },
        )
        
        # Try multiple broad queries to capture all content
        all_documents = []
        seen_content = set()
        
        # Broad queries to retrieve different types of content
        queries = [
            "all agents features pricing capabilities",
            "marketplace integrations Amazon Walmart ONDC",
            "subscription plans pricing tiers",
            "AI agents smart listing text grading image",
            "A+ content video banner lifestyle",
            "competition alerts color variants",
            "onboarding setup getting started",
            "API documentation endpoints",
            "support help troubleshooting",
            "features benefits use cases",
        ]
        
        logger.info(f"Querying knowledge base with {len(queries)} different queries...")
        
        for i, query in enumerate(queries, 1):
            try:
                logger.info(f"[{i}/{len(queries)}] Querying: {query[:50]}...")
                docs = retriever.invoke(query)
                
                for doc in docs:
                    content = doc.page_content
                    # Use hash to avoid duplicates
                    content_hash = hash(content)
                    if content_hash not in seen_content:
                        seen_content.add(content_hash)
                        all_documents.append({
                            'content': content,
                            'metadata': doc.metadata if hasattr(doc, 'metadata') else {}
                        })
                        logger.debug(f"  Added document ({len(content)} chars)")
                
                logger.info(f"  Retrieved {len(docs)} documents, {len(all_documents)} unique so far")
                
            except Exception as e:
                logger.error(f"Error querying with '{query}': {e}")
                continue
        
        # Also try a very generic query to catch anything else
        try:
            logger.info("Performing final broad query...")
            docs = retriever.invoke("MySellerCentral")
            for doc in docs:
                content = doc.page_content
                content_hash = hash(content)
                if content_hash not in seen_content:
                    seen_content.add(content_hash)
                    all_documents.append({
                        'content': content,
                        'metadata': doc.metadata if hasattr(doc, 'metadata') else {}
                    })
        except Exception as e:
            logger.warning(f"Error in final query: {e}")
        
        logger.info(f"\nTotal unique documents retrieved: {len(all_documents)}")
        
        # Create markdown content
        markdown_content = f"""# MySellerCentral Knowledge Base Content

**Extracted on:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Knowledge Base ID:** {KNOWLEDGE_BASE_ID}
**Total Documents:** {len(all_documents)}

---

"""
        
        # Add each document
        for i, doc in enumerate(all_documents, 1):
            markdown_content += f"""## Document {i}

"""
            # Add metadata if available
            if doc.get('metadata'):
                markdown_content += "**Metadata:**\n"
                for key, value in doc['metadata'].items():
                    markdown_content += f"- {key}: {value}\n"
                markdown_content += "\n"
            
            # Add content
            content = doc['content']
            markdown_content += f"{content}\n\n"
            markdown_content += "---\n\n"
        
        # Save to file
        output_file = os.path.join(project_root, "knowledge_base_content.md")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        logger.info(f"\n✅ Successfully extracted {len(all_documents)} documents")
        logger.info(f"📄 Saved to: {output_file}")
        
        return output_file, len(all_documents)
        
    except Exception as e:
        logger.error(f"Error extracting knowledge base content: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    try:
        # Get Knowledge Base ID from environment
        KNOWLEDGE_BASE_ID = get_knowledge_base_id()
        
        print("=" * 80)
        print("KNOWLEDGE BASE CONTENT EXTRACTION")
        print("=" * 80)
        print(f"\nKnowledge Base ID: {KNOWLEDGE_BASE_ID}")
        print(f"Region: {REGION}\n")
        
        output_file, doc_count = extract_knowledge_base_content()
        
        print("\n" + "=" * 80)
        print(f"✅ Extraction completed successfully!")
        print(f"   Documents extracted: {doc_count}")
        print(f"   Output file: {output_file}")
        print("=" * 80)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Extraction interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)











