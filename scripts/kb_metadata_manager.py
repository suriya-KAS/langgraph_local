#!/usr/bin/env python3
"""
Knowledge Base Metadata Manager for AWS Bedrock Knowledge Base.

This script fetches data sources from the Knowledge Base and saves only
created_at and updated_at timestamps to the cache.

The script reads the Knowledge Base ID from environment variables:
- Primary: KNOWLEDGE_BASE_ID (from .env file)
- Fallback: BEDROCK_KNOWLEDGE_BASE_ID (from .env file)
- Alternative: Command line argument or default value

Region can be specified via:
- AWS_DEFAULT_REGION or AWS_REGION (from .env file)
- Command line argument
- Default: us-east-1

Data sources are saved to chatbotCache/data_sources/ directory.
"""

import boto3
from urllib.parse import urlparse
from datetime import datetime
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
project_root = Path(__file__).parent.parent
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(env_file)

# Cache directory for storing KB metadata
CACHE_DIR = project_root / "chatbotCache"


class KnowledgeBaseMetadataManager:
    """Complete metadata management for Bedrock Knowledge Base."""
    
    def __init__(self, knowledge_base_id: str, region: str = 'us-east-1', cache_dir: Path = None):
        self.kb_id = knowledge_base_id
        self.region = region
        self.bedrock_agent = boto3.client('bedrock-agent', region_name=region)
        self.bedrock_agent_runtime = boto3.client('bedrock-agent-runtime', region_name=region)
        self.s3 = boto3.client('s3', region_name=region)
        
        # Setup cache directory
        self.cache_dir = cache_dir or CACHE_DIR
        self.cache_dir.mkdir(exist_ok=True)
        
        # Create subdirectory for data sources
        (self.cache_dir / "data_sources").mkdir(exist_ok=True)
    
    def get_kb_info(self):
        """Get knowledge base level metadata."""
        response = self.bedrock_agent.get_knowledge_base(
            knowledgeBaseId=self.kb_id
        )
        
        kb = response['knowledgeBase']
        return {
            'kb_id': kb['knowledgeBaseId'],
            'name': kb['name'],
            'description': kb.get('description'),
            'status': kb['status'],
            'created_at': kb['createdAt'].isoformat(),
            'updated_at': kb['updatedAt'].isoformat(),
            'role_arn': kb['roleArn']
        }
    
    def get_data_sources(self):
        """Get all data sources with only created_at and updated_at timestamps."""
        response = self.bedrock_agent.list_data_sources(
            knowledgeBaseId=self.kb_id
        )
        
        sources = []
        for ds in response['dataSourceSummaries']:
            # Get detailed info to access createdAt
            detail = self.bedrock_agent.get_data_source(
                knowledgeBaseId=self.kb_id,
                dataSourceId=ds['dataSourceId']
            )
            
            ds_data = detail['dataSource']
            
            # Extract created_at from detailed response, fallback to summary if not available
            created_at = None
            if ds_data.get('createdAt'):
                created_at = ds_data['createdAt'].isoformat()
            elif ds.get('createdAt'):
                created_at = ds['createdAt'].isoformat()
            
            sources.append({
                'data_source_id': ds['dataSourceId'],
                'name': ds['name'],
                'created_at': created_at,
                'updated_at': ds['updatedAt'].isoformat()
            })
        
        return sources
    
    def get_documents_with_metadata(self, query: str, num_results: int = 20):
        """
        Retrieve documents with complete metadata.
        
        Args:
            query: Search query for retrieval
            num_results: Number of results to return
        
        Returns:
            List of documents with full metadata
        """
        # Retrieve from knowledge base
        response = self.bedrock_agent_runtime.retrieve(
            knowledgeBaseId=self.kb_id,
            retrievalQuery={'text': query},
            retrievalConfiguration={
                'vectorSearchConfiguration': {
                    'numberOfResults': num_results
                }
            }
        )
        
        documents = []
        for result in response['retrievalResults']:
            doc = {
                'content_preview': result['content']['text'][:300],
                'relevance_score': result['score'],
                'kb_metadata': result.get('metadata', {})
            }
            
            # Get S3 location
            if result['location']['type'] == 'S3':
                s3_uri = result['location']['s3Location']['uri']
                doc['s3_uri'] = s3_uri
                
                # Get file metadata from S3
                try:
                    file_meta = self._get_s3_file_metadata(s3_uri)
                    doc.update(file_meta)
                except Exception as e:
                    doc['metadata_error'] = str(e)
            
            documents.append(doc)
        
        return documents
    
    def list_all_files_in_kb(self):
        """List all files across all data sources."""
        all_files = []
        
        # Get all data sources
        sources = self.get_data_sources()
        
        for source in sources:
            bucket = source['bucket_name']
            prefixes = source.get('inclusion_prefixes', [''])
            
            for prefix in prefixes:
                files = self._list_s3_files(bucket, prefix)
                for file in files:
                    file['data_source'] = source['name']
                    all_files.append(file)
        
        return all_files
    
    def _get_s3_file_metadata(self, s3_uri: str):
        """Get metadata for a specific S3 file."""
        parsed = urlparse(s3_uri)
        bucket = parsed.netloc
        key = parsed.path.lstrip('/')
        
        response = self.s3.head_object(Bucket=bucket, Key=key)
        
        return {
            'file_name': key.split('/')[-1],
            'file_path': key,
            'file_size_bytes': response['ContentLength'],
            'file_size_mb': round(response['ContentLength'] / (1024 * 1024), 2),
            'file_size_kb': round(response['ContentLength'] / 1024, 2),
            'last_modified': response['LastModified'].isoformat(),
            'content_type': response.get('ContentType'),
            'etag': response['ETag'].strip('"'),
            'storage_class': response.get('StorageClass', 'STANDARD')
        }
    
    def _list_s3_files(self, bucket: str, prefix: str):
        """List all files in S3 bucket with prefix."""
        files = []
        paginator = self.s3.get_paginator('list_objects_v2')
        
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            if 'Contents' not in page:
                continue
            
            for obj in page['Contents']:
                # Skip folders
                if obj['Key'].endswith('/'):
                    continue
                
                files.append({
                    'file_name': obj['Key'].split('/')[-1],
                    'file_path': obj['Key'],
                    'file_size_bytes': obj['Size'],
                    'file_size_mb': round(obj['Size'] / (1024 * 1024), 2),
                    'last_modified': obj['LastModified'].isoformat(),
                    'etag': obj['ETag'].strip('"'),
                    's3_uri': f"s3://{bucket}/{obj['Key']}"
                })
        
        return files
    
    def save_data_sources_to_cache(self, data: list, filename: str = None):
        """
        Save data sources to cache directory.
        
        Args:
            data: List of data sources to save
            filename: Optional custom filename (defaults to timestamp-based name)
        """
        cache_subdir = self.cache_dir / "data_sources"
        cache_subdir.mkdir(exist_ok=True)
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"data_sources_{timestamp}.json"
        
        filepath = cache_subdir / filename
        
        # Add metadata about the cache entry
        cache_data = {
            'kb_id': self.kb_id,
            'region': self.region,
            'cached_at': datetime.now().isoformat(),
            'data_sources': data
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, default=str)
        
        return filepath
    
    def get_latest_cache(self):
        """
        Get the most recent cached data sources.
        
        Returns:
            Dict with cached data, or None if no cache exists
        """
        cache_subdir = self.cache_dir / "data_sources"
        if not cache_subdir.exists():
            return None
        
        # Find most recent cache file
        cache_files = sorted(cache_subdir.glob("data_sources_*.json"), reverse=True)
        if not cache_files:
            return None
        
        with open(cache_files[0], 'r', encoding='utf-8') as f:
            return json.load(f)


def main():
    """Main function to demonstrate usage."""
    # Get KB ID from environment variable (KNOWLEDGE_BASE_ID or BEDROCK_KNOWLEDGE_BASE_ID)
    # Fall back to command line argument or default
    kb_id = os.getenv('KNOWLEDGE_BASE_ID') or os.getenv('BEDROCK_KNOWLEDGE_BASE_ID')
    kb_id_source = 'environment variable' if kb_id else None
    
    if not kb_id:
        kb_id = sys.argv[1] if len(sys.argv) > 1 else None
        kb_id_source = 'command line argument' if kb_id else None
    
    if not kb_id:
        # Try to get from utility function (will raise error if not set)
        try:
            from utils.kb_utils import get_knowledge_base_id
            kb_id = get_knowledge_base_id()
            kb_id_source = 'environment variable (via utility)'
        except ValueError as e:
            print("=" * 60)
            print("✗ Error: Knowledge Base ID not found!")
            print("=" * 60)
            print(str(e))
            print("\nPlease set KNOWLEDGE_BASE_ID or BEDROCK_KNOWLEDGE_BASE_ID in your .env file")
            print("Or pass it as a command line argument: python kb_metadata_manager.py <KB_ID> [REGION]")
            sys.exit(1)
    
    # Get region from environment variable or command line argument or default
    region = os.getenv('AWS_DEFAULT_REGION') or os.getenv('AWS_REGION')
    region_source = 'environment variable' if region else None
    
    if not region:
        region = sys.argv[2] if len(sys.argv) > 2 else None
        region_source = 'command line argument' if region else None
    
    if not region:
        region = 'us-east-1'  # Default fallback
        region_source = 'default value'
    
    print("=" * 60)
    print("Knowledge Base Metadata Manager")
    print("=" * 60)
    print(f"Knowledge Base ID: {kb_id} (from {kb_id_source})")
    print(f"Region: {region} (from {region_source})\n")
    
    try:
        manager = KnowledgeBaseMetadataManager(kb_id, region)
        
        print(f"\n📁 Cache directory: {manager.cache_dir}\n")
        
        # Get data sources with only created_at and updated_at
        print("-" * 60)
        print("Data Sources (created_at, updated_at only)")
        print("-" * 60)
        sources = manager.get_data_sources()
        print(json.dumps(sources, indent=2, default=str))
        
        # Save data sources to cache
        cache_file = manager.save_data_sources_to_cache(sources, f"data_sources_{kb_id}.json")
        print(f"\n💾 Saved data sources to: {cache_file}")
        
        print("\n" + "=" * 60)
        print("✓ Data sources retrieval complete!")
        print(f"✓ Saved to: {manager.cache_dir}/data_sources/")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()








