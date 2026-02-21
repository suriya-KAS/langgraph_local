"""
Intent Extraction and Component Generation
Extracts intent from LLM response and generates structured components
"""
import re
import json
import os
import sys
import time
from typing import Dict, Optional, List, Tuple, TYPE_CHECKING
# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from utils.logger_config import get_logger

DEBUG_LOG_PATH = os.path.join(project_root, ".cursor", "debug.log")
DEBUG_LOG_FALLBACK = os.path.join(project_root, "logs", "agent_debug.ndjson")


def _debug_log_write(payload: dict) -> None:
    """Append one NDJSON line to debug log (primary path, fallback to logs/)."""
    line = json.dumps(payload) + "\n"
    for path in (DEBUG_LOG_PATH, DEBUG_LOG_FALLBACK):
        try:
            d = os.path.dirname(path)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(path, "a") as f:
                f.write(line)
                f.flush()
            return
        except Exception as e:
            logger.warning("Debug log write failed for %s: %s", path, e)

if TYPE_CHECKING:
    from src.services.agent_service import AgentService

from src.core.models import (
    IntentType, MessageComponents, AgentCard, QuickAction, 
    ActionType, MessageType
)
from src.services.currency_service import CurrencyService

# Initialize logger
logger = get_logger(__name__)

# Constants
LAUNCH_AGENT_URL = "https://mysellercentral.com"


class IntentExtractor:
    """Extracts intent and generates UI components from LLM response"""
    
    def __init__(self, agent_service: Optional['AgentService'] = None):
        """
        Initialize IntentExtractor
        
        Args:
            agent_service: Optional AgentService instance (for dependency injection/testing)
        """
        logger.info("Initializing IntentExtractor")
        # Lazy import to avoid circular dependencies
        if agent_service is None:
            logger.info("Creating new AgentService instance")
            # Import here to avoid circular dependency
            import sys
            import os
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            from src.services.agent_service import AgentService
            agent_service = AgentService()
        else:
            logger.info("Using provided AgentService instance")
        
        self.agent_service = agent_service
        logger.info("IntentExtractor initialization completed")
    
    @property
    def AGENT_DATABASE(self) -> Dict[str, Dict]:
        """
        Get agent database (lazy-loaded from knowledge base via AgentService)
        Note: This property queries KB. Use get_agent_database(cache_only=True) for cache-only access.
        
        Returns:
            Dict mapping agent_id to agent info
        """
        return self.agent_service.get_all_agents()
    
    def get_agent_database(self, cache_only: bool = False) -> Dict[str, Dict]:
        """
        Get agent database with option to use cache only (no KB query).
        Use cache_only=True for agent card generation to avoid KB queries.
        
        Args:
            cache_only: If True, only use cache file, don't query KB
        
        Returns:
            Dict mapping agent_id to agent info
        """
        return self.agent_service.get_all_agents(cache_only=cache_only)
    
    def extract_intent(self, user_message: str, llm_data, agent_db: Optional[Dict[str, Dict]] = None) -> Tuple[str, Optional[str]]:
        """
        Extract intent from user message and LLM structured response.
        Supports both new structured format (dict) and legacy string format.
        
        Args:
            user_message: User's input message
            llm_data: Either:
                - Dict with 'reply', 'intent', 'agentId' (new structured format)
                - str (legacy format - LLM response text)
            agent_db: Optional pre-fetched agent database dict. If None, will be fetched internally.
            
        Returns:
            Tuple of (intent: str, agent_id: Optional[str])
        """
        logger.info(f"Extracting intent from user message: {user_message[:100]}...")
        # Handle new structured format
        if isinstance(llm_data, dict):
            logger.debug("Processing structured format (dict) from LLM")
            llm_intent = llm_data.get('intent', 'general_query')
            llm_agent_id = llm_data.get('agentId')
            llm_reply = llm_data.get('reply', '')
            logger.debug(f"LLM provided intent: {llm_intent}, agentId: {llm_agent_id}")
            
            # Map LLM intent to IntentType enum
            intent_map = {
                'agent_suggestion': IntentType.AGENT_SUGGESTION,
                'pricing_query': IntentType.PRICING_QUERY,
                'marketplace_query': IntentType.MARKETPLACE_QUERY,
                'feature_query': IntentType.FEATURE_QUERY,
                'support': IntentType.SUPPORT,
                'general_query': IntentType.GENERAL_QUERY,
            }
            
            intent = intent_map.get(llm_intent, IntentType.GENERAL_QUERY)
            logger.debug(f"Mapped intent to: {intent}")
            
            # Validate agentId if provided - handle both list and string
            agent_id = None
            # Use provided agent_db or fetch it (cache-only mode for agent validation)
            if agent_db is None:
                agent_db = self.get_agent_database(cache_only=True)  # Cache only for agent validation
            if llm_agent_id:
                # Handle list case (multiple agents)
                if isinstance(llm_agent_id, list):
                    # Take first valid agent from the list
                    for agent in llm_agent_id:
                        if isinstance(agent, str) and agent in agent_db:
                            agent_id = agent
                            break
                    # If none found in database, use first one anyway (will be validated later)
                    if not agent_id and len(llm_agent_id) > 0:
                        agent_id = llm_agent_id[0] if isinstance(llm_agent_id[0], str) else None
                # Handle string case (single agent)
                elif isinstance(llm_agent_id, str):
                    # Check if agent exists in database
                    if llm_agent_id in agent_db:
                        agent_id = llm_agent_id
                    else:
                        # Try to find similar agent from response text
                        agent_id = self._extract_agent_from_text(llm_reply, agent_db=agent_db)
            
            # Safety: If LLM says agent_suggestion but no valid agentId, try to extract
            if intent == IntentType.AGENT_SUGGESTION and not agent_id:
                logger.debug("Intent is AGENT_SUGGESTION but no agentId, attempting extraction from text")
                agent_id = self._extract_agent_from_text(llm_reply, agent_db=agent_db)
                if not agent_id:
                    agent_id = self._extract_agent_from_text(user_message, agent_db=agent_db)
                if agent_id:
                    logger.info(f"Extracted agent_id from text: {agent_id}")
            
            # Fallback: If LLM didn't provide structured data or gave general_query, 
            # use keyword matching as validation
            if not llm_intent or llm_intent == 'general_query':
                logger.debug("LLM intent is general_query or missing, using keyword fallback")
                fallback_intent = self._keyword_fallback(user_message, llm_reply, agent_db=agent_db)
                if fallback_intent != IntentType.GENERAL_QUERY:
                    logger.info(f"Keyword fallback detected intent: {fallback_intent}")
                    intent = fallback_intent
                    if not agent_id:
                        agent_id = self._extract_agent_from_text(llm_reply, agent_db=agent_db) or self._extract_agent_from_text(user_message, agent_db=agent_db)
            
            # Special case: Even if LLM says general_query, check if user is asking to list all agents
            # This ensures we show all agents when user explicitly asks
            user_lower = user_message.lower()
            list_all_keywords = [
                "list all agents", "list agents", "show all agents", "show agents",
                "what agents", "which agents", "available agents", "all agents",
                "agent catalog", "agent list", "agents available", "all ai agents"
            ]
            if any(keyword in user_lower for keyword in list_all_keywords):
                logger.info("User explicitly asked to list all agents - overriding intent to AGENT_SUGGESTION")
                intent = IntentType.AGENT_SUGGESTION
            
            logger.info(f"Final extracted intent: {intent}, agent_id: {agent_id}")
            return intent, agent_id
        
        # Legacy format: string response (backward compatibility)
        else:
            logger.debug("Processing legacy format (string) from LLM")
            llm_response = str(llm_data)
            user_lower = user_message.lower()
            response_lower = llm_response.lower()
            
            # Use provided agent_db or fetch it for legacy format
            if agent_db is None:
                agent_db = self.get_agent_database(cache_only=True)
            
            # Agent-related keywords
            if any(keyword in user_lower for keyword in ["agent", "tool", "feature", "help with", "improve"]):
                if any(keyword in response_lower for keyword in ["image", "photo", "picture"]):
                    agent_id = self._extract_agent_from_text(llm_response, agent_db=agent_db)
                    logger.info(f"Legacy format: Detected AGENT_SUGGESTION with agent_id: {agent_id}")
                    return IntentType.AGENT_SUGGESTION, agent_id
                agent_id = self._extract_agent_from_text(llm_response, agent_db=agent_db)
                logger.info(f"Legacy format: Detected AGENT_SUGGESTION with agent_id: {agent_id}")
                return IntentType.AGENT_SUGGESTION, agent_id
            
            # Pricing keywords
            if any(keyword in user_lower for keyword in ["price", "cost", "pricing", "how much", "fee"]):
                logger.info("Legacy format: Detected PRICING_QUERY")
                return IntentType.PRICING_QUERY, None
            
            # Marketplace keywords
            if any(keyword in user_lower for keyword in ["marketplace", "amazon", "walmart", "shopify", "ondc"]):
                logger.info("Legacy format: Detected MARKETPLACE_QUERY")
                return IntentType.MARKETPLACE_QUERY, None
            
            # Feature keywords
            if any(keyword in user_lower for keyword in ["feature", "capability", "what can", "how does"]):
                logger.info("Legacy format: Detected FEATURE_QUERY")
                return IntentType.FEATURE_QUERY, None
            
            # Support keywords
            if any(keyword in user_lower for keyword in ["help", "support", "issue", "problem", "error"]):
                logger.info("Legacy format: Detected SUPPORT")
                return IntentType.SUPPORT, None
            
            logger.info("Legacy format: Defaulting to GENERAL_QUERY")
            return IntentType.GENERAL_QUERY, None
    
    def _keyword_fallback(self, user_message: str, llm_response: str, agent_db: Optional[Dict[str, Dict]] = None) -> str:
        """
        Fallback keyword-based intent detection when structured output fails.
        
        Args:
            user_message: User's input message
            llm_response: LLM's response text
            agent_db: Optional pre-fetched agent database dict. If None, will be fetched internally.
            
        Returns:
            Detected intent type
        """
        user_lower = user_message.lower()
        response_lower = llm_response.lower()
        
        # Check for "list all agents" queries - should be AGENT_SUGGESTION
        agent_list_keywords = [
            "list all agents", "list agents", "show all agents", "show agents",
            "what agents", "which agents", "available agents", "all agents",
            "agent catalog", "agent list", "agents available", "all ai agents"
        ]
        if any(keyword in user_lower for keyword in agent_list_keywords):
            return IntentType.AGENT_SUGGESTION
        
        # Check if response mentions multiple agents (indicates listing query)
        if agent_db is None:
            agent_db = self.get_agent_database(cache_only=True)
        agent_count = sum(1 for agent_id, agent_info in agent_db.items() 
                         if agent_info["name"].lower() in response_lower)
        if agent_count >= 3:  # If response mentions 3+ agents, likely a listing query
            return IntentType.AGENT_SUGGESTION
        
        if any(keyword in user_lower for keyword in ["price", "cost", "pricing", "how much", "fee"]):
            return IntentType.PRICING_QUERY
        if any(keyword in user_lower for keyword in ["marketplace", "amazon", "walmart", "shopify", "ondc"]):
            return IntentType.MARKETPLACE_QUERY
        if any(keyword in user_lower for keyword in ["feature", "capability", "what can", "how does"]):
            return IntentType.FEATURE_QUERY
        if any(keyword in user_lower for keyword in ["help", "support", "issue", "problem", "error"]):
            return IntentType.SUPPORT
        
        # Check for general agent queries
        if any(keyword in user_lower for keyword in ["agent", "ai agent", "tool", "feature"]):
            return IntentType.AGENT_SUGGESTION
        
        return IntentType.GENERAL_QUERY
    
    def _extract_agent_from_text(self, text: str, agent_db: Optional[Dict[str, Dict]] = None) -> Optional[str]:
        """
        Extract agent ID from any text (user message or LLM response).
        Uses multiple strategies for robust detection.
        Returns the first agent found.
        
        Args:
            text: Text to search for agent mentions
            agent_db: Optional pre-fetched agent database dict. If None, will be fetched internally.
            
        Returns:
            Agent ID if found, None otherwise
        """
        logger.debug(f"Extracting agent from text: {text[:100]}...")
        agents = self._extract_all_agents_from_text(text, agent_db=agent_db)
        result = agents[0] if agents else None
        if result:
            logger.debug(f"Found agent in text: {result}")
        else:
            logger.debug("No agent found in text")
        return result
    
    def _extract_all_agents_from_text(self, text: str, agent_db: Optional[Dict[str, Dict]] = None) -> List[str]:
        """
        Extract all agent IDs mentioned in text.
        
        Args:
            text: Text to search for agent mentions
            agent_db: Optional pre-fetched agent database dict. If None, will be fetched internally.
            
        Returns:
            List of agent IDs found (in order of detection)
        """
        logger.debug(f"Extracting all agents from text (length: {len(text)})")
        text_lower = text.lower()
        detected_agents = []
        found_agent_ids = set()  # Track to avoid duplicates
        
        # Get current agent database (use provided or fetch)
        if agent_db is None:
            agent_db = self.get_agent_database(cache_only=True)
        logger.debug(f"Agent database contains {len(agent_db)} agents")
        
        # Strategy 1: Check for exact agent name matches
        for agent_id, agent_info in agent_db.items():
            if agent_id in found_agent_ids:
                continue
                
            agent_name_lower = agent_info["name"].lower()
            # Check if agent name appears in text (full match)
            if agent_name_lower in text_lower:
                detected_agents.append(agent_id)
                found_agent_ids.add(agent_id)
                continue
            
            # Check for close/exact phrase match: require a distinctive phrase that includes
            # the agent's distinguishing first word (e.g. "text grading", "image grading").
            # This avoids false positives when agents share keywords - e.g. "Text Grading & Enhancement"
            # vs "Image Grading & Enhancement": only "text grading" or "image grading" should match,
            # not "grading enhancement" which appears in both.
            agent_name_words = [w for w in re.split(r"[\s&]+", agent_name_lower) if w and w not in ["agent", "the", "a", "an"]]
            if len(agent_name_words) >= 2:
                distinguisher = agent_name_words[0]
                # Phrases starting with the distinguishing word: "text grading", "image grading", etc.
                distinctive_phrases = [
                    f"{distinguisher} {agent_name_words[i + 1]}"
                    for i in range(len(agent_name_words) - 1)
                    if agent_name_words[i] == distinguisher
                ]
                if distinctive_phrases and any(phrase in text_lower for phrase in distinctive_phrases):
                    detected_agents.append(agent_id)
                    found_agent_ids.add(agent_id)
                    logger.debug(f"Close phrase match: Found {agent_id} via distinctive phrase")
                    continue
            
            # Check if agent ID (with/without hyphens) appears
            agent_id_variants = [
                agent_id,
                agent_id.replace("-", " "),
                agent_id.replace("-", ""),
            ]
            for variant in agent_id_variants:
                if variant in text_lower and agent_id not in found_agent_ids:
                    detected_agents.append(agent_id)
                    found_agent_ids.add(agent_id)
                    break
        
        # Strategy 2: Pattern matching for common agent mentions
        # A+ Content detection (multiple patterns)
        if "a-plus-content" not in found_agent_ids:
            if re.search(r"a\+?\s*(?:content|page|brand)", text_lower) or \
               re.search(r"a\s+plus\s+(?:content|page|brand)", text_lower) or \
               re.search(r"refine.*a\+", text_lower) or \
               re.search(r"a\+.*refine", text_lower):
                detected_agents.append("a-plus-content")
                found_agent_ids.add("a-plus-content")
                logger.debug("Pattern match: Found a-plus-content agent")
        
        # Smart Listing detection
        if "smart-listing" not in found_agent_ids:
            if re.search(r"smart\s+listing", text_lower) or \
               (re.search(r"listing", text_lower) and re.search(r"smart|agent|ai", text_lower)):
                detected_agents.append("smart-listing")
                found_agent_ids.add("smart-listing")
                logger.debug("Pattern match: Found smart-listing agent")
        
        # Lifestyle Image Generator
        if "lifestyle-image-generator" not in found_agent_ids:
            if re.search(r"lifestyle\s+(?:image|photo|picture)", text_lower) or \
               re.search(r"lifestyle\s+generator", text_lower):
                detected_agents.append("lifestyle-image-generator")
                found_agent_ids.add("lifestyle-image-generator")
                logger.debug("Pattern match: Found lifestyle-image-generator agent")
        
        # Image Grading/Enhancement (check for image-related keywords)
        if "image-grading-enhancement" not in found_agent_ids:
            if re.search(r"image\s+(?:grading|grade|enhance|refine|improve)", text_lower) or \
               re.search(r"grade\s+(?:image|photo|picture)", text_lower) or \
               re.search(r"refine\s+(?:image|photo|picture)", text_lower) or \
               re.search(r"improve\s+(?:image|photo|picture)", text_lower):
                detected_agents.append("image-grading-enhancement")
                found_agent_ids.add("image-grading-enhancement")
                logger.debug("Pattern match: Found image-grading-enhancement agent")
        
        logger.info(f"Extracted {len(detected_agents)} agents from text: {detected_agents}")
        return detected_agents
    
    def extract_agent_from_response(self, llm_response: str, agent_db: Optional[Dict[str, Dict]] = None) -> Optional[str]:
        """
        Extract agent ID from LLM response (legacy method, uses _extract_agent_from_text).
        
        Args:
            llm_response: LLM's response text
            agent_db: Optional pre-fetched agent database dict. If None, will be fetched internally.
            
        Returns:
            Agent ID if found, None otherwise
        """
        return self._extract_agent_from_text(llm_response, agent_db=agent_db)
    
    def _get_agent_cost(self, agent_info: Dict, currency: str) -> float:
        """
        Extract agent cost based on currency.
        Handles both old format (cost as number) and new format (cost as dict with INR/USD).
        
        Args:
            agent_info: Agent information dictionary
            currency: Currency code (INR or USD)
            
        Returns:
            Cost as float in the specified currency
        """
        cost_data = agent_info.get("cost", 0)
        
        # New format: cost is a dict with INR and USD
        if isinstance(cost_data, dict):
            cost = cost_data.get(currency, cost_data.get("INR", 0))  # Fallback to INR if currency not found
            logger.debug(f"Extracted cost from dict: {cost} {currency}")
            return float(cost)
        # Old format: cost is a number (backward compatibility)
        else:
            cost = float(cost_data)
            logger.debug(f"Using cost as number (backward compatibility): {cost}")
            return cost
    
    def _generate_agent_quick_actions(self, agent_id: str, agent_info: Dict) -> List[QuickAction]:
        """
        Generate agent-specific quick actions based on agent type
        
        Args:
            agent_id: Agent identifier
            agent_info: Agent information dictionary
            
        Returns:
            List of QuickAction objects specific to this agent
        """
        agent_name_lower = agent_info.get("name", "").lower()
        agent_id_lower = agent_id.lower()
        
        # Generate unique quick actions based on agent type
        if "listing" in agent_id_lower or "listing" in agent_name_lower:
            return [
                # QuickAction(
                #     label="How to use?",
                #     message=f"How do I use {agent_info.get('name', 'this agent')}?",
                #     actionType=ActionType.MESSAGE,
                #     icon="❓"
                # ),
                # QuickAction(
                #     label="See Example",
                #     message=f"Show me an example of {agent_info.get('name', 'this agent')}",
                #     actionType=ActionType.MESSAGE,
                #     icon="💡"
                # ),
                # QuickAction(
                #     label="Marketplaces",
                #     message=f"Which marketplaces does {agent_info.get('name', 'this agent')} support?",
                #     actionType=ActionType.MESSAGE,
                #     icon="🏪"
                # ),
                QuickAction(
                    label="Launch Agent",
                    url="https://mysellercentral.com/ai-agents/listing-generation",
                    actionType=ActionType.URL,
                    icon="🚀"
                )
            ]
        elif "text" in agent_id_lower and "grading" in agent_id_lower:
            return [
                # QuickAction(
                #     label="How it works?",
                #     message=f"How does {agent_info.get('name', 'this agent')} improve my listings?",
                #     actionType=ActionType.MESSAGE,
                #     icon="🔍"
                # ),
                # QuickAction(
                #     label="Try it",
                #     message=None,
                #     actionType=ActionType.LAUNCH_AGENT,
                #     icon="✨"
                # ),
                QuickAction(
                    label="Launch Agent",
                    url="https://mysellercentral.com/ai-agents/text-grading",
                    actionType=ActionType.URL,
                    icon="🚀"
                )
            ]
        elif "image" in agent_id_lower and "grading" in agent_id_lower:
            return [
                # QuickAction(
                #     label="Image Tips",
                #     message=f"What image standards does {agent_info.get('name', 'this agent')} check?",
                #     actionType=ActionType.MESSAGE,
                #     icon="📸"
                # ),
                # QuickAction(
                #     label="Use Now",
                #     message=None,
                #     actionType=ActionType.LAUNCH_AGENT,
                #     icon="✨"
                # ),
                QuickAction(
                    label="Launch Agent",
                    url="https://mysellercentral.com/ai-agents/image-grading",
                    actionType=ActionType.URL,
                    icon="🚀"
                )
            ]
        elif "lifestyle" in agent_id_lower:
            return [
                # QuickAction(
                #     label="Scene Options",
                #     message=f"What lifestyle scenes can {agent_info.get('name', 'this agent')} create?",
                #     actionType=ActionType.MESSAGE,
                #     icon="🏠"
                # ),
                # QuickAction(
                #     label="Generate",
                #     message=None,
                #     actionType=ActionType.LAUNCH_AGENT,
                #     icon="🎨"
                # ),
                QuickAction(
                    label="Launch Agent",
                    url="https://mysellercentral.com/ai-agents/lifestyle-image-generation",
                    actionType=ActionType.URL,
                    icon="🚀"
                )
            ]
        elif "infographic" in agent_id_lower:
            return [
                # QuickAction(
                #     label="Learn More",
                #     message=f"Tell me more about {agent_info.get('name', 'this agent')}",
                #     actionType=ActionType.MESSAGE,
                #     icon="📊"
                # ),
                # QuickAction(
                #     label="Create Infographic",
                #     message=None,
                #     actionType=ActionType.LAUNCH_AGENT,
                #     icon="🎯"
                # ),
                QuickAction(
                    label="Launch Agent",
                    url="https://mysellercentral.com/ai-agents/infographic-image-generation",
                    actionType=ActionType.URL,
                    icon="🚀"
                )
            ]
        elif "banner" in agent_id_lower:
            return [
                # QuickAction(
                #     label="Banner Specs",
                #     message=f"What are the banner specifications for {agent_info.get('name', 'this agent')}?",
                #     actionType=ActionType.MESSAGE,
                #     icon="📐"
                # ),
                # QuickAction(
                #     label="Create Banner",
                #     message=None,
                #     actionType=ActionType.LAUNCH_AGENT,
                #     icon="🎯"
                # ),
                QuickAction(
                    label="Launch Agent",
                    url="https://mysellercentral.com/ai-agents/banner-collage-generation",
                    actionType=ActionType.URL,
                    icon="🚀"
                )
            ]
        elif "color" in agent_id_lower or "variant" in agent_id_lower:
            return [
                # QuickAction(
                #     label="Color Options",
                #     message=f"What color options does {agent_info.get('name', 'this agent')} support?",
                #     actionType=ActionType.MESSAGE,
                #     icon="🌈"
                # ),
                # QuickAction(
                #     label="Generate Variants",
                #     message=None,
                #     actionType=ActionType.LAUNCH_AGENT,
                #     icon="✨"
                # ),
                QuickAction(
                    label="Launch Agent",
                    url="https://mysellercentral.com/ai-agents/color-variants",
                    actionType=ActionType.URL,
                    icon="🚀"
                )
            ]
        elif "a-plus" in agent_id_lower or "a+content" in agent_id_lower.replace("-", ""):
            return [
                # QuickAction(
                #     label="Templates",
                #     message=f"What templates does {agent_info.get('name', 'this agent')} offer?",
                #     actionType=ActionType.MESSAGE,
                #     icon="📋"
                # ),
                # QuickAction(
                #     label="Create A+ Content",
                #     message=None,
                #     actionType=ActionType.LAUNCH_AGENT,
                #     icon="⭐"
                # ),
                QuickAction(
                    label="Launch Agent",
                    url="https://mysellercentral.com/ai-agents/aplus-content",
                    actionType=ActionType.URL,
                    icon="🚀"
                )
            ]
        elif "video" in agent_id_lower:
            return [
                # QuickAction(
                #     label="Video Types",
                #     message=f"What types of videos can {agent_info.get('name', 'this agent')} create?",
                #     actionType=ActionType.MESSAGE,
                #     icon="🎥"
                # ),
                # QuickAction(
                #     label="Create Video",
                #     message=None,
                #     actionType=ActionType.LAUNCH_AGENT,
                #     icon="🎬"
                # ),
                QuickAction(
                    label="Launch Agent",
                    url="https://mysellercentral.com/ai-agents/video-generation",
                    actionType=ActionType.URL,
                    icon="🚀"
                )
            ]
        elif "competition" in agent_id_lower or "alert" in agent_id_lower:
            return [
                # QuickAction(
                #     label="Setup Alerts",
                #     message=f"How do I set up {agent_info.get('name', 'this agent')}?",
                #     actionType=ActionType.MESSAGE,
                #     icon="🔔"
                # ),
                # QuickAction(
                #     label="Track ASINs",
                #     message=None,
                #     actionType=ActionType.LAUNCH_AGENT,
                #     icon="📊"
                # ),
                QuickAction(
                    label="Launch Agent",
                    url="https://mysellercentral.com/ai-agents/competition-analysis",
                    actionType=ActionType.URL,
                    icon="🚀"
                )
            ]
        else:
            # Default quick actions for unknown agent types
            return [
                # QuickAction(
                #     label="Learn More",
                #     message=f"Tell me more about {agent_info.get('name', 'this agent')}",
                #     actionType=ActionType.MESSAGE,
                #     icon="ℹ️"
                # ),
                # QuickAction(
                #     label="Use Agent",
                #     message=None,
                #     actionType=ActionType.LAUNCH_AGENT,
                #     icon="✨"
                # ),
                # QuickAction(
                #     label="Launch Agent",
                #     url=LAUNCH_AGENT_URL,
                #     actionType=ActionType.URL,
                #     icon="🚀"
                # )
            ]
    
    def generate_components(
        self,
        intent,
        llm_response: str,
        wallet_balance: float,
        user_message: str,
        agent_id: Optional[str] = None,
        llm_agent_ids: Optional[List[str]] = None,
        currency: Optional[str] = None,
        country: Optional[str] = None,
        timezone: Optional[str] = None,
        cache_only: bool = False,
        agent_db: Optional[Dict[str, Dict]] = None,
        query_category: Optional[str] = None,
    ) -> Optional[MessageComponents]:
        """
        Generate UI components based on intent and response
        
        Args:
            intent: Detected intent (IntentType enum or string)
            llm_response: LLM response (text or dict with 'reply' key)
            wallet_balance: Current wallet balance
            user_message: Original user message
            agent_id: Optional pre-extracted agent ID (from structured response)
            currency: Optional currency code (INR/USD). If not provided, will be detected from country/timezone
            country: Optional country code for currency detection
            timezone: Optional timezone for currency detection
            cache_only: If True, only use cache file, don't query KB (for backward compatibility)
            agent_db: Optional pre-fetched agent database dict. If None, will be fetched internally.
            query_category: Orchestrator category (e.g. product_detail). When product_detail, agent cards
                are generated from agents mentioned in the reply text only.
            
        Returns:
            MessageComponents if applicable, None otherwise
        """
        # Detect currency if not provided
        if not currency:
            if country or timezone:
                currency = CurrencyService.detect_currency(
                    login_location=None,  # loginLocation not available in fallback
                    country=country,
                    timezone=timezone or "UTC"
                )
            else:
                currency = "INR"  # Default to INR
                logger.warning("No currency, country, or timezone provided - defaulting to INR")
        
        currency_symbol = CurrencyService.get_currency_symbol(currency)
        logger.info(f"Generating components for intent: {intent}, wallet_balance: {wallet_balance}, currency: {currency}")
        components = MessageComponents()
        
        # Normalize intent to IntentType enum for comparison
        if isinstance(intent, str):
            # Convert string to IntentType enum
            intent_map = {
                'agent_suggestion': IntentType.AGENT_SUGGESTION,
                'pricing_query': IntentType.PRICING_QUERY,
                'marketplace_query': IntentType.MARKETPLACE_QUERY,
                'feature_query': IntentType.FEATURE_QUERY,
                'support': IntentType.SUPPORT,
                'general_query': IntentType.GENERAL_QUERY,
            }
            intent = intent_map.get(intent, IntentType.GENERAL_QUERY)
        
        # Extract reply text if llm_response is a dict
        reply_text = llm_response
        if isinstance(llm_response, dict):
            reply_text = llm_response.get('reply', '')
        
        # Check if this is a "list all agents" query (used for AGENT_SUGGESTION to skip cards)
        list_all_keywords = [
            "list all agents", "list agents", "list down all agents", "list down agents",
            "list down every agents", "list every agents", "every agents",
            "show all agents", "show agents", "show me all agents", "show me agents",
            "what agents", "which agents", "available agents", "all agents",
            "agent catalog", "agent list", "agents available", "all ai agents",
            "tell me about agents", "tell me about all agents"
        ]
        user_lower = user_message.lower()
        is_list_all_query = any(kw in user_lower for kw in list_all_keywords)
        matched_kw = [kw for kw in list_all_keywords if kw in user_lower]
        # #region agent log
        _debug_log_write({"sessionId": "debug-session", "hypothesisId": "H1", "location": "intent_extractor.generate_components", "message": "list-all check", "data": {"user_message": user_message[:80], "is_list_all_query": is_list_all_query, "matched_keywords": matched_kw}, "timestamp": int(time.time() * 1000)})
        # #endregion
        
        # Only treat as "list all" if user explicitly asks for it
        # Don't treat multiple agents in response as "list all" - user might have asked for specific agents
        # The is_list_all_query flag is already set above based on explicit user keywords
        
        # product_detail, insights_kb, analytics_reporting: agent cards from agents mentioned in the response text
        reply_driven_categories = ("product_detail", "insights_kb", "analytics_reporting")
        if query_category in reply_driven_categories and reply_text:
            if agent_db is None:
                agent_db = self.get_agent_database(cache_only=cache_only)
            reply_mentioned = self._extract_all_agents_from_text(reply_text, agent_db=agent_db)
            valid_agents = [a for a in reply_mentioned if a in agent_db]
            if agent_id and agent_id in valid_agents and valid_agents[0] != agent_id:
                valid_agents = [a for a in valid_agents if a != agent_id]
                valid_agents.insert(0, agent_id)
            if valid_agents:
                logger.info(f"{query_category}: generating agent cards from reply content: {valid_agents}")
                if len(valid_agents) >= 2 and len(valid_agents) <= 3:
                    suggested_agents = []
                    for aid in valid_agents:
                        agent_info = agent_db[aid]
                        cost = self._get_agent_cost(agent_info, currency)
                        wallet_after = wallet_balance - cost
                        quick_actions = self._generate_agent_quick_actions(aid, agent_info)
                        suggested_agents.append(AgentCard(
                            agentId=aid,
                            name=agent_info["name"],
                            icon=agent_info["icon"],
                            cost=cost,
                            currency=currency,
                            currencySymbol=currency_symbol,
                            walletAfter=max(0, wallet_after),
                            features=agent_info["features"],
                            action="launch_agent",
                            marketplace=agent_info["marketplace"],
                            quickActions=quick_actions
                        ))
                    components.suggestedAgents = suggested_agents
                    logger.info(f"Added {len(suggested_agents)} agents to suggestedAgents ({query_category}, reply-driven)")
                else:
                    primary_agent_id = valid_agents[0]
                    agent_info = agent_db[primary_agent_id]
                    cost = self._get_agent_cost(agent_info, currency)
                    wallet_after = wallet_balance - cost
                    quick_actions = self._generate_agent_quick_actions(primary_agent_id, agent_info)
                    components.agentCard = AgentCard(
                        agentId=primary_agent_id,
                        name=agent_info["name"],
                        icon=agent_info["icon"],
                        cost=cost,
                        currency=currency,
                        currencySymbol=currency_symbol,
                        walletAfter=max(0, wallet_after),
                        features=agent_info["features"],
                        action="launch_agent",
                        marketplace=agent_info["marketplace"],
                        quickActions=quick_actions
                    )
                    if len(valid_agents) > 1:
                        suggested_agents = []
                        for other_agent_id in valid_agents[1:]:
                            if other_agent_id in agent_db:
                                other_agent_info = agent_db[other_agent_id]
                                other_cost = self._get_agent_cost(other_agent_info, currency)
                                other_wallet_after = wallet_balance - other_cost
                                other_quick_actions = self._generate_agent_quick_actions(other_agent_id, other_agent_info)
                                suggested_agents.append(AgentCard(
                                    agentId=other_agent_id,
                                    name=other_agent_info["name"],
                                    icon=other_agent_info["icon"],
                                    cost=other_cost,
                                    currency=currency,
                                    currencySymbol=currency_symbol,
                                    walletAfter=max(0, other_wallet_after),
                                    features=other_agent_info["features"],
                                    action="launch_agent",
                                    marketplace=other_agent_info["marketplace"],
                                    quickActions=other_quick_actions
                                ))
                        components.suggestedAgents = suggested_agents
                    logger.info(f"Added agentCard + {len(components.suggestedAgents or [])} suggestedAgents ({query_category}, reply-driven)")
        
        # Generate agent card for agent suggestions (non–product_detail or when product_detail had no agents in reply)
        elif intent == IntentType.AGENT_SUGGESTION:
            logger.info("Generating agent card for AGENT_SUGGESTION intent")
            if agent_db is None:
                agent_db = self.get_agent_database(cache_only=cache_only)
            reply_mentioned = self._extract_all_agents_from_text(reply_text, agent_db=agent_db) if reply_text else []
            # #region agent log
            _debug_log_write({"sessionId": "debug-session", "hypothesisId": "H3", "location": "intent_extractor.generate_components", "message": "reply-mentioned agents", "data": {"reply_mentioned_agents": reply_mentioned, "reply_len": len(reply_text) if reply_text else 0}, "timestamp": int(time.time() * 1000)})
            # #endregion
            
            # Use provided agent_db or fetch it (use cache_only mode for agent cards - no KB query)
            if agent_db is None:
                agent_db = self.get_agent_database(cache_only=cache_only)
            
            # SOURCE OF TRUTH: Agent cards are generated ONLY from agents explicitly mentioned in the reply content.
            # - List-all queries: show no cards (reply text already lists agents; user does not want bottom cards).
            # - Single/multi-agent: show cards only for agents the reply text explicitly discusses (no LLM/user fallback).
            if is_list_all_query:
                valid_agents = []
                logger.info("List-all query: no agent cards (reply content is the catalog)")
            elif len(reply_mentioned) > 0:
                valid_agents = [a for a in reply_mentioned if a in agent_db]
                if agent_id and agent_id in valid_agents and valid_agents[0] != agent_id:
                    valid_agents.remove(agent_id)
                    valid_agents.insert(0, agent_id)
                logger.info(f"Using only reply-mentioned agents for cards (content-driven): {valid_agents}")
            else:
                valid_agents = []
                logger.info("No agents explicitly mentioned in reply; no agent cards (no fallback to LLM/user list)")
            
            # #region agent log
            used_reply_instead_of_list_all = is_list_all_query and len(reply_mentioned) > 0
            _debug_log_write({"sessionId": "debug-session", "runId": "post-fix", "hypothesisId": "H2", "location": "intent_extractor.generate_components", "message": "valid_agents after list-all", "data": {"valid_agents": valid_agents, "valid_count": len(valid_agents), "used_list_all_override": is_list_all_query, "used_reply_instead_of_list_all": used_reply_instead_of_list_all}, "timestamp": int(time.time() * 1000)})
            # #endregion
            
            # Special case: When 2-3 agents detected, show all equally (no primary)
            if len(valid_agents) >= 2 and len(valid_agents) <= 3 and not is_list_all_query:
                logger.info(f"Multiple agents detected ({len(valid_agents)}) - showing all equally")
                # Don't set agentCard, put all in suggestedAgents
                suggested_agents = []
                for agent_id in valid_agents:
                    if agent_id in agent_db:
                        agent_info = agent_db[agent_id]
                        cost = self._get_agent_cost(agent_info, currency)
                        wallet_after = wallet_balance - cost
                        quick_actions = self._generate_agent_quick_actions(agent_id, agent_info)
                        
                        suggested_agents.append(AgentCard(
                            agentId=agent_id,
                            name=agent_info["name"],
                            icon=agent_info["icon"],
                            cost=cost,
                            currency=currency,
                            currencySymbol=currency_symbol,
                            walletAfter=max(0, wallet_after),
                            features=agent_info["features"],
                            action="launch_agent",
                            marketplace=agent_info["marketplace"],
                            quickActions=quick_actions
                        ))
                components.suggestedAgents = suggested_agents
                logger.info(f"Added all {len(suggested_agents)} agents to suggestedAgents (no primary agentCard)")
            else:
                # Original logic for single agent or many agents
                # Use first agent as primary, rest as suggestions
                primary_agent_id = valid_agents[0] if valid_agents else None
                
                if primary_agent_id and primary_agent_id in agent_db:
                    logger.info(f"Creating agent card for primary agent: {primary_agent_id}")
                    agent_info = agent_db[primary_agent_id]
                    cost = self._get_agent_cost(agent_info, currency)
                    wallet_after = wallet_balance - cost
                    logger.debug(f"Agent cost: {cost} {currency}, wallet after: {wallet_after}")
                    quick_actions = self._generate_agent_quick_actions(primary_agent_id, agent_info)
                    
                    components.agentCard = AgentCard(
                        agentId=primary_agent_id,
                        name=agent_info["name"],
                        icon=agent_info["icon"],
                        cost=cost,
                        currency=currency,
                        currencySymbol=currency_symbol,
                        walletAfter=max(0, wallet_after),  # Ensure non-negative
                        features=agent_info["features"],
                        action="launch_agent",
                        marketplace=agent_info["marketplace"],
                        quickActions=quick_actions
                    )
                    
                    # Add ALL other detected agents as suggestions (not just extras)
                    # This ensures all mentioned agents are shown prominently
                    if len(valid_agents) > 1:
                        suggested_agents = []
                        for other_agent_id in valid_agents[1:]:  # Skip first one (already in agentCard)
                            if other_agent_id in agent_db:
                                other_agent_info = agent_db[other_agent_id]
                                other_cost = self._get_agent_cost(other_agent_info, currency)
                                other_wallet_after = wallet_balance - other_cost
                                other_quick_actions = self._generate_agent_quick_actions(other_agent_id, other_agent_info)
                                
                                suggested_agents.append(AgentCard(
                                    agentId=other_agent_id,
                                    name=other_agent_info["name"],
                                    icon=other_agent_info["icon"],
                                    cost=other_cost,
                                    currency=currency,
                                    currencySymbol=currency_symbol,
                                    walletAfter=max(0, other_wallet_after),
                                    features=other_agent_info["features"],
                                    action="launch_agent",
                                    marketplace=other_agent_info["marketplace"],
                                    quickActions=other_quick_actions
                                ))
                        components.suggestedAgents = suggested_agents
                        logger.info(f"Added {len(suggested_agents)} agents to suggestedAgents")
                else:
                    logger.warning(f"No valid primary agent found. Valid agents: {valid_agents}")
        
        # Generate quick actions based on intent
        # Note: For AGENT_SUGGESTION, quickActions are now per-agent (in each AgentCard)
        # So we don't set global quickActions for agent suggestions
        if intent == IntentType.PRICING_QUERY:
            components.quickActions = [
                QuickAction(
                    label="View Plans",
                    message="Show me all pricing plans",
                    actionType=ActionType.MESSAGE
                ),
                QuickAction(
                    label="Start Trial",
                    message="How do I start a trial?",
                    actionType=ActionType.MESSAGE
                )
            ]
        elif intent == IntentType.GENERAL_QUERY:
            components.quickActions = [
                QuickAction(
                    label="Browse Agents",
                    message="What AI agents are available?",
                    actionType=ActionType.MESSAGE
                ),
                
                # QuickAction(
                #     label="View Marketplaces",
                #     message="Which marketplaces do you support?",
                #     actionType=ActionType.MESSAGE
                # )
            ]
        
        # Return components only if there's something to show
        if components.agentCard or (components.suggestedAgents and len(components.suggestedAgents) > 0) or (components.quickActions and len(components.quickActions) > 0):
            logger.info("Components generated successfully")
            return components
        
        logger.info("No components generated")
        return None
    
    def extract_pricing_info(self, llm_response: str) -> Optional[Dict]:
        """Extract pricing information from response"""
        # This would parse pricing information from the LLM response
        # For now, return None - can be enhanced with regex/NLP
        return None
    
    def extract_marketplace_info(self, llm_response: str) -> Optional[Dict]:
        """Extract marketplace information from response"""
        # This would parse marketplace info from the LLM response
        return None

