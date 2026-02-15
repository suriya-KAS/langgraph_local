"""
Agent Service with Hash-Based Change Detection
Fetches and caches agent information from knowledge base
"""
import os
import json
import hashlib
import re
from typing import Dict, Optional, List
from datetime import datetime
from dotenv import load_dotenv
from langchain_aws import ChatBedrock, AmazonKnowledgeBasesRetriever
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import boto3
import os
import sys
# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from utils.logger_config import get_logger

# Load environment variables from .env file (for local development)
# boto3 automatically picks up AWS credentials from environment variables or IAM roles
load_dotenv()

# Initialize logger
logger = get_logger(__name__)


class AgentService:
    """Service for fetching and caching agent data from knowledge base with hash-based change detection"""
    
    def __init__(self):
        """Initialize agent service with KB retriever and LLM"""
        logger.info("Initializing AgentService")
        try:
            # Initialize knowledge base retriever
            from utils.kb_utils import get_knowledge_base_id
            knowledge_base_id = get_knowledge_base_id()
            logger.info(f"Initializing knowledge base retriever with ID: {knowledge_base_id}")
            self.retriever = AmazonKnowledgeBasesRetriever(
                knowledge_base_id=knowledge_base_id,
                retrieval_config={
                    "vectorSearchConfiguration": {
                        "numberOfResults": 20,
                    }
                },
            )
            
            # Initialize LLM for parsing agent data
            region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
            logger.info(f"Initializing Bedrock client in region: {region}")
            bedrock_client = boto3.client(
                service_name="bedrock-runtime",
                region_name=region
            )
            model_id = "mistral.mistral-large-2402-v1:0"
            self.llm = ChatBedrock(
                model_id=model_id,
                client=bedrock_client,
                model_kwargs={"max_tokens": 4000, "temperature": 0.1}  # Low temp for structured extraction
            )
            logger.info(f"Initialized LLM model: {model_id}")
            
            # Cache
            self._agents_cache: Optional[Dict] = None
            self._kb_content_hash: Optional[str] = None
            # Store cache in project root - check both possible cache file names
            project_root = os.path.join(os.path.dirname(__file__), '../..')
            # Priority: agents_cache.json (user-provided) then .agents_cache.json (auto-generated)
            self._cache_file_primary = os.path.join(project_root, 'agents_cache.json')
            self._cache_file = os.path.join(project_root, '.agents_cache.json')
            logger.info(f"Primary cache file path: {self._cache_file_primary}")
            logger.info(f"Fallback cache file path: {self._cache_file}")
            
            # Load cache from disk on initialization
            self._load_cache()
            logger.info("AgentService initialization completed successfully")
        except Exception as e:
            logger.error(f"Error during AgentService initialization: {e}", exc_info=True)
            raise

    async def _retrieve_kb_docs_async(self, query: str):
        """
        Async KB retrieval (preferred). Falls back to thread executor if needed.
        """
        if hasattr(self.retriever, "ainvoke"):
            return await self.retriever.ainvoke(query)
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop, create new one (shouldn't happen in async context, but safe fallback)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return await loop.run_in_executor(None, self.retriever.invoke, query)
    
    def _load_cache(self):
        """Load cache from disk if available - checks both cache file locations"""
        # Try primary cache file first (agents_cache.json)
        cache_file_to_load = None
        if os.path.exists(self._cache_file_primary):
            cache_file_to_load = self._cache_file_primary
            logger.info(f"Attempting to load cache from primary file: {self._cache_file_primary}")
        elif os.path.exists(self._cache_file):
            cache_file_to_load = self._cache_file
            logger.info(f"Attempting to load cache from fallback file: {self._cache_file}")
        else:
            logger.info("No cache file found, starting with empty cache")
            return
        
        try:
            with open(cache_file_to_load, 'r') as f:
                data = json.load(f)
                self._agents_cache = data.get('agents')
                self._kb_content_hash = data.get('hash')
                cached_at = data.get('cached_at', 'unknown')
                agent_count = len(self._agents_cache) if self._agents_cache else 0
                logger.info(f"✅ Successfully loaded agent cache from disk - {agent_count} agents cached at: {cached_at}")
                logger.info(f"📋 Cache file hash: {self._kb_content_hash[:16] if self._kb_content_hash else 'None'}...")
        except Exception as e:
            logger.error(f"Cache load failed: {e}", exc_info=True)
            self._agents_cache = None
            self._kb_content_hash = None
    
    def _save_cache(self, agents: Dict, content_hash: str):
        """Save cache to disk (saves to primary cache file: agents_cache.json)"""
        logger.info(f"Saving agent cache to disk - {len(agents)} agents")
        try:
            cache_data = {
                'agents': agents,
                'hash': content_hash,
                'cached_at': datetime.now().isoformat()
            }
            # Save to primary cache file (agents_cache.json)
            with open(self._cache_file_primary, 'w') as f:
                json.dump(cache_data, f, indent=2)
            logger.info(f"✅ Successfully saved agent cache to disk: {self._cache_file_primary} (hash: {content_hash[:16]}...)")
        except Exception as e:
            logger.error(f"Cache save failed: {e}", exc_info=True)
    
    def _name_to_slug(self, name: str) -> str:
        """Convert agent name to slug (agent ID format)"""
        slug = name.lower()
        # Remove special characters, keep only alphanumeric and spaces
        slug = re.sub(r'[^a-z0-9\s]', '', slug)
        # Replace spaces with hyphens
        slug = re.sub(r'\s+', '-', slug)
        # Remove leading/trailing hyphens
        slug = slug.strip('-')
        return slug
    
    def _parse_marketplace_list(self, marketplace_data) -> List[str]:
        """Parse marketplace information into a list"""
        if isinstance(marketplace_data, list):
            return marketplace_data
        elif isinstance(marketplace_data, str):
            # Handle strings like "Amazon, ONDC, eBay" or "Amazon only" or "All marketplaces"
            if "all marketplaces" in marketplace_data.lower():
                return ["Amazon", "Walmart", "Shopify", "ONDC", "eBay"]
            elif "only" in marketplace_data.lower():
                # Extract marketplace name before "only"
                match = re.search(r'([A-Za-z]+)\s+only', marketplace_data)
                return [match.group(1)] if match else []
            else:
                # Split by comma
                marketplaces = [m.strip() for m in marketplace_data.split(",")]
                return marketplaces
        return []
    
    def _get_icon_for_agent(self, agent_name: str) -> str:
        """Get appropriate icon emoji for agent based on name"""
        name_lower = agent_name.lower()
        
        icon_map = {
            'listing': '📝',
            'text': '📝',
            'image': '🖼️',
            'lifestyle': '🎨',
            'a+': '⭐',
            'a-plus': '⭐',
            'video': '🎥',
            'competition': '🔔',
            'alert': '🔔',
            'banner': '🎯',
            'color': '🌈',
            'variant': '🌈',
            'infographic': '📊',
        }
        
        for keyword, icon in icon_map.items():
            if keyword in name_lower:
                return icon
        
        return '🤖'  # Default icon
    
    def _parse_agents_with_llm(self, kb_text: str) -> Dict[str, Dict]:
        """
        Use LLM to extract structured agent data from knowledge base text
        
        Args:
            kb_text: Text from knowledge base containing agent information
            
        Returns:
            Dict mapping agent_id to agent info
        """
        extraction_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a data extraction assistant. Extract agent information from the provided text and return it as a JSON object.

For each agent, extract:
- id: Agent ID as slug (lowercase, hyphens instead of spaces, e.g., "smart-listing", "a-plus-content")
- name: Full agent name exactly as written
- price: Price as integer (extract number from "₹X per use")
- capabilities: List of capability strings (from Capabilities section, as array)
- marketplace: List of marketplace names (from Marketplace Support section, as array)
- icon: Appropriate emoji icon based on agent type (use one of: 📝 🖼️ 🎨 ⭐ 🎥 🔔 🎯 🌈 📊)

Available icons based on agent type:
- Listing/Text: 📝
- Image/Grading: 🖼️
- Lifestyle: 🎨
- A+ Content: ⭐
- Video: 🎥
- Competition/Alerts: 🔔
- Banner: 🎯
- Color/Variant: 🌈
- Infographic: 📊

Return ONLY valid JSON in this format:
{{
  "agents": [
    {{
      "id": "smart-listing",
      "name": "Smart Listing Agent",
      "icon": "📝",
      "price": 30,
      "capabilities": ["List products instantly", "AI-written titles"],
      "marketplace": ["Amazon", "ONDC", "eBay"]
    }}
  ]
}}

Extract ALL agents mentioned in the text."""),
            ("human", "Extract all agent information from this text:\n\n{kb_text}")
        ])
        
        chain = extraction_prompt | self.llm | StrOutputParser()
        
        try:
            logger.info("Invoking LLM to parse agent data from knowledge base")
            kb_text_length = len(kb_text)
            logger.debug(f"Knowledge base text length: {kb_text_length} characters")
            
            response = chain.invoke({"kb_text": kb_text})
            logger.info("Received response from LLM for agent parsing")
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                logger.debug("Found JSON pattern in LLM response, attempting to parse")
                parsed = json.loads(json_match.group(0))
                
                # Convert to expected format
                agents_dict = {}
                for agent in parsed.get("agents", []):
                    agent_id = agent.get("id", self._name_to_slug(agent.get("name", "")))
                    agents_dict[agent_id] = {
                        "name": agent.get("name", ""),
                        "icon": agent.get("icon", self._get_icon_for_agent(agent.get("name", ""))),
                        "cost": agent.get("price", 0),
                        "marketplace": self._parse_marketplace_list(agent.get("marketplace", [])),
                        "features": agent.get("capabilities", [])
                    }
                    logger.debug(f"Parsed agent: {agent_id} - {agents_dict[agent_id]['name']}")
                
                logger.info(f"Successfully parsed {len(agents_dict)} agents from knowledge base")
                return agents_dict
            else:
                logger.warning("No JSON pattern found in LLM response")
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON from LLM response: {e}")
            logger.debug(f"LLM response (first 500 chars): {response[:500]}...")
        except Exception as e:
            logger.error(f"Error parsing agent data with LLM: {e}", exc_info=True)
        
        return {}
    
    def get_all_agents(self, cache_only: bool = False) -> Dict[str, Dict]:
        """
        Get all agents, with smart caching based on KB content hash.
        Uses cached file from disk when hash changes (avoids LLM parsing for performance).
        
        Args:
            cache_only: If True, only use cache file, don't query KB. Use this for agent cards.
                       If False, query KB first to check for changes, then use cache if hash matches.
        
        Returns:
            Dict mapping agent_id to agent info
        """
        try:
            # OPTIMIZATION: Check in-memory cache first (fastest path)
            if self._agents_cache:
                logger.debug(f"✅ Using in-memory cache ({len(self._agents_cache)} agents)")
                return self._agents_cache.copy()
            
            # Try to load from cache file on disk (check both locations)
            cache_file_to_load = None
            if os.path.exists(self._cache_file_primary):
                cache_file_to_load = self._cache_file_primary
            elif os.path.exists(self._cache_file):
                cache_file_to_load = self._cache_file
            
            if cache_file_to_load:
                try:
                    with open(cache_file_to_load, 'r') as f:
                        cache_data = json.load(f)
                        cached_agents = cache_data.get('agents', {})
                        cached_hash = cache_data.get('hash', '')
                        cached_at = cache_data.get('cached_at', 'unknown')
                        
                        if cached_agents:
                            agent_count = len(cached_agents)
                            logger.info(f"✅ Successfully loaded {agent_count} agents from cache file (cached at: {cached_at})")
                            logger.info(f"📋 Cache file hash: {cached_hash[:16] if cached_hash else 'None'}...")
                            
                            # Update in-memory cache
                            self._agents_cache = cached_agents
                            self._kb_content_hash = cached_hash
                            
                            # If cache_only mode, return immediately without KB query
                            if cache_only:
                                logger.debug("Cache-only mode: Returning cached agents without KB query")
                                return cached_agents.copy()
                            
                            # If not cache_only, continue to check KB for changes
                        else:
                            logger.warning("Cache file exists but contains no agents")
                except Exception as e:
                    logger.error(f"Error reading cache file: {e}", exc_info=True)
            else:
                logger.warning(f"Cache file not found at: {self._cache_file_primary} or {self._cache_file}")
            
            # If cache_only mode and we have cache, we already returned above
            # If cache_only mode and no cache, use fallback
            if cache_only:
                logger.warning("⚠️ Cache-only mode: No cache available - using fallback hardcoded agents")
                fallback_agents = self._get_fallback_agents()
                logger.info(f"Returning {len(fallback_agents)} fallback agents")
                return fallback_agents
            
            # Not cache_only mode: Query KB to check for changes
            logger.info("Fetching all agents from knowledge base")
            # Query KB for agent section
            query = "AI-Powered Agents catalog list all agents with price capabilities marketplace support"
            logger.debug(f"Querying knowledge base with: {query}")
            # Prefer async KB access; if we're in a running event loop we can't block it.
            # For this legacy sync method, avoid KB calls when possible; otherwise use a safe fallback.
            try:
                import asyncio
                loop = asyncio.get_running_loop()
                # Running under ASGI/event-loop: do NOT block; rely on cache/fallback.
                logger.warning("Running event loop detected; skipping live KB query in sync get_all_agents(). Use cache_only=True or implement async usage.")
                docs = []
            except RuntimeError:
                # No running loop: safe to run async retrieval.
                docs = asyncio.run(self._retrieve_kb_docs_async(query))
            logger.info(f"Retrieved {len(docs)} documents from knowledge base")
            
            # Combine all document content
            kb_text = "\n\n".join(doc.page_content for doc in docs)
            kb_text_length = len(kb_text)
            logger.debug(f"Combined knowledge base text length: {kb_text_length} characters")
            
            # Compute hash of KB content
            current_hash = hashlib.sha256(kb_text.encode()).hexdigest()
            logger.debug(f"Computed KB content hash: {current_hash[:16]}...")
            
            # If hash matches cached hash and we have cache, return cached data (KB unchanged)
            if self._kb_content_hash and self._kb_content_hash == current_hash and self._agents_cache:
                agent_count = len(self._agents_cache) if self._agents_cache else 0
                logger.info(f"✅ Agent cache HIT - Hash matches! Using cached data from memory ({agent_count} agents, hash: {current_hash[:16]}...)")
                return self._agents_cache.copy()  # Return copy to prevent mutation
            
            # Hash changed or no cache - use cached file from disk instead of LLM parsing
            if self._kb_content_hash and self._kb_content_hash != current_hash:
                logger.info(f"⚠️ Knowledge base content hash changed - old: {self._kb_content_hash[:16] if self._kb_content_hash else 'None'}..., new: {current_hash[:16]}...")
                logger.info("📁 Loading agents from cached file (agents_cache.json) instead of LLM parsing")
            elif not self._kb_content_hash:
                logger.info("📁 No cached hash found - loading agents from cached file (agents_cache.json)")
            else:
                logger.info("📁 Cache miss - loading agents from cached file (agents_cache.json)")
            
            # Try to load from cache file on disk again (in case it wasn't loaded earlier)
            if not self._agents_cache:
                cache_file_to_load = None
                if os.path.exists(self._cache_file_primary):
                    cache_file_to_load = self._cache_file_primary
                    logger.info(f"Reading cached agents from primary file: {self._cache_file_primary}")
                elif os.path.exists(self._cache_file):
                    cache_file_to_load = self._cache_file
                    logger.info(f"Reading cached agents from fallback file: {self._cache_file}")
                
                if cache_file_to_load:
                    try:
                        with open(cache_file_to_load, 'r') as f:
                            cache_data = json.load(f)
                            cached_agents = cache_data.get('agents', {})
                            cached_hash = cache_data.get('hash', '')
                            cached_at = cache_data.get('cached_at', 'unknown')
                            
                            if cached_agents:
                                agent_count = len(cached_agents)
                                logger.info(f"✅ Successfully loaded {agent_count} agents from cache file (cached at: {cached_at})")
                                logger.info(f"📋 Cache file hash: {cached_hash[:16] if cached_hash else 'None'}...")
                                
                                # Update in-memory cache
                                self._agents_cache = cached_agents
                                self._kb_content_hash = cached_hash  # Use cached hash, not current hash
                                
                                return cached_agents.copy()  # Return copy
                            else:
                                logger.warning("Cache file exists but contains no agents")
                    except Exception as e:
                        logger.error(f"Error reading cache file: {e}", exc_info=True)
            
            # If cache file doesn't exist or failed to load, use fallback hardcoded agents
            logger.warning("⚠️ No cache file available - using fallback hardcoded agents")
            fallback_agents = self._get_fallback_agents()
            logger.info(f"Returning {len(fallback_agents)} fallback agents")
            
            # Save fallback agents to cache file for future use
            try:
                fallback_hash = hashlib.sha256("fallback".encode()).hexdigest()  # Dummy hash for fallback
                self._save_cache(fallback_agents, fallback_hash)
                logger.info("Saved fallback agents to cache file for future use")
            except Exception as e:
                logger.error(f"Failed to save fallback agents to cache: {e}", exc_info=True)
            
            return fallback_agents
            
        except Exception as e:
            logger.error(f"Error fetching agents from knowledge base: {e}", exc_info=True)
            # Return cached data if available, or fallback
            if self._agents_cache:
                logger.info("Returning cached agents from memory due to error")
                return self._agents_cache.copy()
            else:
                # Try to load from cache file one more time (check both locations)
                cache_file_to_load = None
                if os.path.exists(self._cache_file_primary):
                    cache_file_to_load = self._cache_file_primary
                elif os.path.exists(self._cache_file):
                    cache_file_to_load = self._cache_file
                
                if cache_file_to_load:
                    try:
                        with open(cache_file_to_load, 'r') as f:
                            cache_data = json.load(f)
                            cached_agents = cache_data.get('agents', {})
                            if cached_agents:
                                logger.info(f"Loaded {len(cached_agents)} agents from cache file as fallback")
                                return cached_agents
                    except Exception as e2:
                        logger.error(f"Failed to load from cache file: {e2}")
                
                logger.info("No cache available, returning fallback agents")
                return self._get_fallback_agents()
    
    def get_agent_by_id(self, agent_id: str) -> Optional[Dict]:
        """Get a specific agent by ID"""
        logger.info(f"Fetching agent by ID: {agent_id}")
        agents = self.get_all_agents()
        agent = agents.get(agent_id)
        if agent:
            logger.info(f"Found agent: {agent_id} - {agent.get('name', 'Unknown')}")
        else:
            logger.warning(f"Agent not found: {agent_id}")
        return agent
    
    def invalidate_cache(self):
        """Manually invalidate cache (for testing/force refresh)"""
        logger.info("Invalidating agent cache")
        self._agents_cache = None
        self._kb_content_hash = None
        try:
            # Remove both cache files if they exist
            removed = False
            if os.path.exists(self._cache_file_primary):
                os.remove(self._cache_file_primary)
                logger.info(f"Removed primary cache file: {self._cache_file_primary}")
                removed = True
            if os.path.exists(self._cache_file):
                os.remove(self._cache_file)
                logger.info(f"Removed fallback cache file: {self._cache_file}")
                removed = True
            if not removed:
                logger.info("No cache files found to remove")
        except Exception as e:
            logger.error(f"Error removing cache file: {e}", exc_info=True)
    
    def _get_fallback_agents(self) -> Dict[str, Dict]:
        """Fallback hardcoded agents if KB fetch/parse fails"""
        logger.info("Using fallback hardcoded agents")
        return {
            "smart-listing": {
                "name": "Smart Listing Agent",
                "icon": "📝",
                "cost": {"INR": 30, "USD": 0.40},
                "marketplace": ["Amazon", "ONDC", "eBay"],
                "features": ["List products instantly", "Image + audio → instant listing", "AI-written titles, bullets, descriptions"]
            },
            "text-grading-enhancement": {
                "name": "Text Grading & Enhancement Agent",
                "icon": "📝",
                "cost": {"INR": 20, "USD": 0.25},
                "marketplace": ["Amazon"],
                "features": ["Analyze and enhance listing text", "AI grades title, bullets & description", "SEO and clarity checks"]
            },
            "image-grading-enhancement": {
                "name": "Image Grading & Enhancement Agent",
                "icon": "🖼️",
                "cost": {"INR": 25, "USD": 0.30},
                "marketplace": ["Amazon"],
                "features": ["Check image quality", "AI evaluates image quality, background, clarity", "Visual improvement suggestions"]
            },
            "lifestyle-image-generator": {
                "name": "Lifestyle Image Generator Agent",
                "icon": "🎨",
                "cost": {"INR": 20, "USD": 0.25},
                "marketplace": ["All marketplaces"],
                "features": ["Convert product photos into lifestyle scenes", "AI-generated lifestyle backgrounds", "Multiple scene options"]
            },
            "infographic-image-generator": {
                "name": "Infographic Image Generator Agent",
                "icon": "📊",
                "cost": {"INR": 20, "USD": 0.25},
                "marketplace": ["All marketplaces"],
                "features": ["Explain product visually through infographics", "Visual key feature highlights", "Auto + prompt-based creation"]
            },
            "color-variants-generator": {
                "name": "Color Variants Generator Agent",
                "icon": "🌈",
                "cost": {"INR": 10, "USD": 0.15},
                "marketplace": ["All marketplaces"],
                "features": ["Auto-generate product images in multiple color themes", "Generates realistic variants", "Enhances catalog diversity"]
            },
            "a-plus-content": {
                "name": "A+ Content Agent",
                "icon": "⭐",
                "cost": {"INR": 50, "USD": 0.60},
                "marketplace": ["Amazon"],
                "features": ["A+ content creation", "Premium templates", "Media-rich content"]
            },
            "a-plus-video-content": {
                "name": "A+ Video Content Agent",
                "icon": "🎥",
                "cost": {"INR": 50, "USD": 0.60},
                "marketplace": ["Amazon"],
                "features": ["Create engaging A+ brand videos with AI", "Media-rich auto video generation", "Template-based creation"]
            },
            "competition-alerts": {
                "name": "Competition Alerts Agent",
                "icon": "🔔",
                "cost": {"INR": 10, "USD": 0.15},
                "marketplace": ["Amazon"],
                "features": ["Tracks ASINs and competitor listings", "Smart Change Detection", "Daily/Real-time Notifications"]
            },
            "banner-image-generator": {
                "name": "Banner Image Generator Agent",
                "icon": "🎯",
                "cost": {"INR": 20, "USD": 0.25},
                "marketplace": ["All marketplaces"],
                "features": ["Create stunning banner images", "Banner creation from multiple images", "2:1 aspect ratio for banners"]
            }
        }

