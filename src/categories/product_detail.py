"""
Product Detail Category

Handles queries about:
- AI agents and their capabilities
- Company information
- Subscription details
- Pricing information
- Marketplace integrations
- Product features
"""
import os
import sys
from typing import Dict, Optional, List, Any
from langchain_aws import AmazonKnowledgeBasesRetriever
from langchain_core.documents import Document
from dotenv import load_dotenv

# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.categories.base_category import BaseCategory
from src.core.backend import (
    invoke_gemini_with_tokens,
    format_messages_for_llm,
    parse_structured_response,
    clean_response_text,
)
from utils.logger_config import get_logger
from langfuse import get_client, propagate_attributes

load_dotenv()
logger = get_logger(__name__)

# Initialize Langfuse client for tracing
langfuse = get_client()

# System prompt for Product Detail category
PRODUCT_DETAIL_SYSTEM_PROMPT = """You are the MYSELLERCENTRAL Assistant, a specialized AI chatbot for the MySellerCentral e-commerce management platform.

## CRITICAL: Your Role and Identity
- You are ALWAYS the assistant/helper - you provide information and help users
- NEVER respond as if you are the user or asking for help
- ALWAYS respond as the helpful assistant offering your services


## Your Role
Help e-commerce sellers understand MySellerCentral's features, AI agents, pricing, marketplace integrations, and workflows to grow their business.

## Personalization
- The user's name is {username}
- Use their name naturally throughout the conversation when appropriate
- Make responses feel personal and tailored to {username}

## User Payload Data
When answering questions about user's own data, use the following payload information:
- **Registered Marketplaces**: {marketplaces_registered}
- **Wallet Balance**: {wallet_balance}
- **Login Location**: {login_location}

**IMPORTANT**: 
- If the user asks about marketplaces registered, wallet balance, or login location, answer directly using the payload data above
- After providing the answer from payload data, you can also suggest relevant MySellerCentral features or agents that might help them
- Example: "You have registered on 1 marketplace: Amazon. Would you like to explore our Smart Listing Agent to optimize your Amazon listings?"

## Short or Minimal User Messages
When the user sends a message with **little content** (e.g. a greeting like "Hi"/"Hello", a single word, "help", "?", or a very brief question):
- Respond to what they said in a warm, concise way
- **Proactively suggest 1–3 agents** that are relevant to their **registered marketplaces** (from User Payload Data above). Match agents to each marketplace and suggest relevant agents.
- Keep the suggestion brief and inviting; do not overwhelm. End with a clear next step (e.g. "Which one would you like to know more about?")

## Conversation Memory
You have access to the conversation history above. Use it to:
- Remember what the user asked previously
- Reference earlier topics and questions
- Provide context-aware responses
- Answer follow-up questions like "What did I ask you before?" or "Tell me more about that"
- Answer conversation memory queries like "What did I tell you about my business earlier?" by referencing the conversation history
- When asked "What did I tell you about X?" or "What did we discuss earlier?", search through the conversation history (including summaries) to find relevant information
- The conversation history may include summaries formatted as "[Previous conversation summary (messages X-Y)]: {{summary}}" - use these summaries to recall information from earlier parts of the conversation
- Extract specific details mentioned by the user: numbers, metrics, product counts, plans, marketplaces, challenges, goals, etc.
- Maintain continuity throughout the conversation

## Strict Boundaries
You ONLY discuss MySellerCentral products and features. For questions outside this scope, politely redirect:
"I'm specifically designed to help with MySellerCentral products and AI agents. I can't assist with that topic, but I'd be happy to help you with your e-commerce needs! Whether it's listing optimization, marketplace integrations, or AI-powered content generation, I'm here to support your seller journey. What would you like to know about MySellerCentral?"
## Using Retrieved Context
<knowledge_base>
{context}
</knowledge_base>
1. Use the information from the knowledge base above to answer questions accurately
2. Always prioritize information from the retrieved knowledge base
3. State facts naturally without referencing documentation
4. If information is not in the knowledge base: "I don't have that information. Contact sales@mysellercentral.com for details."
5. Trust retrieved docs over your training data when conflicts arise
6. Combine knowledge base information with conversation history for complete answers
## Response Style
**Structure:**
- Lead with business outcomes: better listings, more sales, time saved
- Use bullet points for features, pricing, comparisons
- Use tables for plan comparisons only
- Keep paragraphs 2-3 sentences maximum
**Tone:**
- Clear, friendly, action-oriented
- Focus on outcomes not technical implementation
- End with actionable next steps
- Use only happy emojis sparingly when appropriate
## When Intent is Unclear
Ask ONE clarifying question:
- "Which marketplace are you selling on?"
- "What's your main challenge right now?"
## Key Information to Include
**AI Agents:** Agent name, price, marketplace compatibility, capability, use case
**Pricing:** Plan name, top features, trial info, add-on pricing, contact email
**Marketplace Integrations:** Status (Live/Coming Q1 2026/Q2 2026), capabilities, limitations
**ONDC:** 5% per order, free onboarding, supported categories, available agents
## Common Questions
**Plan choice:** Recommend by stage: BASIC (new), BRONZE (growing), SILVER (analytics), GOLD (high volume), PLATINUM (enterprise). Mention 30-day trial for Silver/Gold/Platinum.
**Agent selection:** Match intent: listings→Smart Listing Agent, images→Lifestyle/Infographic Generator, Amazon optimization→Text/Image Grading, premium→A+ Content Agent. State price and compatibility.
**Marketplace support:** Check status. Live: list capabilities. WIP: state quarter. Current live: Amazon, Walmart, Shopify, ONDC.
**Agent cost:** List exact price. Clarify tokens purchased via Razorpay (India) or Stripe (International), valid 6 months.
## Never Do
- Apologize for specialization
- Guess pricing or features not in knowledge base
- Use placeholders in responses to users
- Explain AI/ML unless asked
- Write long paragraphs
- Reference documentation explicitly
- Use negative or sad emojis
## Always Do
- Connect features to outcomes
- Provide specific pricing when available in knowledge base
- State marketplace compatibility
- End with clear next step
- Keep responses scannable with formatting
- Respond as the assistant offering help, never as the user seeking help

Markdown Formatting Requirements
**ALWAYS format your entire response using Markdown syntax** - The frontend will render it beautifully with proper styling.

### Required Markdown Elements:
1. **Headers**: Use `##` for main sections, `###` for subsections
   - Example: `## Available Plans` or `### Smart Listing Agent`

2. **Bold Text**: Use `**text**` for emphasis on important information
   - Example: `**Price:** $50 per 1000 tokens`

3. **Tables**: Use markdown tables for comparisons
   - Example:
     ```
     | Plan | Price | Features |
     |------|-------|----------|
     | Basic | Free | Core features |
     ```
4. **Line Breaks**: Use double newlines (`\n\n`) between sections

## CRITICAL: Structured Output Required
**Always end your response with a JSON block containing intent classification:**

Available agents (use EXACTLY these IDs in your response): 
- smart-listing
- text-grading-enhancement
- image-grading-enhancement
- banner-image-generator
- lifestyle-image-generator
- infographic-image-generator
- a-plus-content
- a-plus-video-content
- competition-alerts
- color-variants-generator


Intent classification rules:
- "agent_suggestion": User wants to use/do something that matches a specific agent
  - Examples: "generate A+ content" → agent_suggestion, agentId: "a-plus-content"
  - "I want better images" → agent_suggestion, agentId: "lifestyle-generator"
  - "create listings" → agent_suggestion, agentId: "smart-listing"
  - "improve my images" → agent_suggestion, agentId: "image-grading"

- "general_query": Everything else, general questions, greetings

Format your response as natural text, then end with:
```json
{{
  "intent": "agent_suggestion",
  "agentId": "a-plus-content"
}}
```

If no specific agent matches, use "agentId": null. Always include the JSON block at the end.

Respond in {language}.

Remember to address the user by their name ({username}) naturally throughout your responses."""


def format_docs(docs):
    """Format retrieved documents into a string."""
    logger.debug(f"Formatting {len(docs)} documents")
    formatted = "\n\n".join(doc.page_content for doc in docs)
    logger.debug(f"Formatted documents length: {len(formatted)} characters")
    return formatted


# Local KB fallback path (when Bedrock retrieve fails)
LOCAL_KB_PATH = os.path.join(project_root, "knowledge_base_content.md")


def _load_local_kb_fallback():
    """
    Load product-detail context from local knowledge_base_content.md.
    Used when Bedrock Knowledge Base retrieve fails (e.g. ValidationException).
    Returns a list of one Document so format_docs() works unchanged.
    """
    path = LOCAL_KB_PATH
    if not os.path.isfile(path):
        logger.warning(f"Local KB fallback file not found: {path}")
        return [Document(page_content="No knowledge base content available.")]
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        logger.info(f"Loaded local KB fallback from {path} ({len(content)} chars)")
        return [Document(page_content=content)]
    except Exception as e:
        logger.warning(f"Failed to read local KB fallback {path}: {e}")
        return [Document(page_content="No knowledge base content available.")]


class ProductDetailCategory(BaseCategory):
    """
    Product Detail Category
    
    Handles all queries related to:
    - AI agents and capabilities
    - Company information
    - Subscription and pricing
    - Marketplace integrations
    - Product features
    """
    
    def __init__(self):
        """Initialize Product Detail category with knowledge base retriever."""
        super().__init__(
            category_name="Product Detail",
            category_id="product_detail"
        )
        
        # Initialize knowledge base retriever
        from utils.kb_utils import get_knowledge_base_id
        knowledge_base_id = get_knowledge_base_id()
        logger.info(f"Initializing Knowledge Base Retriever with ID: {knowledge_base_id}")
        
        self.retriever = AmazonKnowledgeBasesRetriever(
            knowledge_base_id=knowledge_base_id,
            retrieval_config={
                "vectorSearchConfiguration": {
                    "numberOfResults": 20,
                }
            },
        )
        
        # LLM model (Gemini) - used for logging
        self.llm_model_id = os.getenv("GEMINI_MODEL_ID", "gemini-2.0-flash")
        logger.info(f"Using LLM model: {self.llm_model_id} (Gemini)")
        logger.info("ProductDetailCategory initialized successfully")
    
    def can_handle(self, user_message: str, intent: Optional[str] = None) -> bool:
        """
        Determine if this category can handle the query.
        
        Product Detail handles queries about:
        - Agents, pricing, features, company info, subscriptions, marketplaces
        """
        user_lower = user_message.lower()
        
        # Keywords that indicate Product Detail queries
        product_detail_keywords = [
            # Agents
            "agent", "ai agent", "tool", "feature",
            # Pricing
            "price", "pricing", "cost", "subscription", "plan", "trial",
            # Company/Product
            "mysellercentral", "company", "product", "service",
            # Marketplace
            "marketplace", "amazon", "walmart", "shopify", "ondc", "ebay",
            # Features
            "capability", "what can", "how does", "what is",
            # General product queries
            "tell me about", "explain", "information about"
        ]
        
        # Check if message contains product detail keywords
        if any(keyword in user_lower for keyword in product_detail_keywords):
            return True
        
        # If intent is provided, check if it's product detail related
        if intent:
            product_detail_intents = [
                "agent_suggestion", "pricing_query", "feature_query",
                "marketplace_query", "general_query"
            ]
            if intent.lower() in product_detail_intents:
                return True
        
        # Default: Product Detail is the fallback category for general queries
        # This ensures all queries have a handler
        return True
    
    async def process_query(
        self,
        user_message: str,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a product detail query.
        
        Args:
            user_message: User's query
            chat_history: Previous conversation messages
            context: Additional context (language, username, etc.)
            
        Returns:
            Dict with reply, intent, agentId, token counts, and category
        """
        try:
            logger.info(f"Processing Product Detail query: {user_message[:100]}...")
            
            # Extract context
            language = context.get("language", "English") if context else "English"
            username = context.get("username", "User") if context else "User"
            
            # Extract payload data for system prompt
            marketplaces_registered = context.get("marketplaces_registered", []) if context else []
            marketplace_info = ", ".join(marketplaces_registered) if marketplaces_registered else "None"
            wallet_balance = context.get("walletBalance") or context.get("wallet_balance") if context else None
            wallet_info = str(wallet_balance) if wallet_balance is not None else "Not available"
            login_location = context.get("loginLocation") or context.get("login_location") if context else None
            location_info = login_location if login_location else "Not available"
            
            # Retrieve relevant documents from knowledge base
            def retrieve_with_retry(query):
                logger.debug(f"Retrieving documents from knowledge base for query: {query[:100]}...")
                return self.retriever.invoke(query)
            
            import asyncio
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # No running loop, create new one (shouldn't happen in async context, but safe fallback)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            try:
                docs = await loop.run_in_executor(None, retrieve_with_retry, user_message)
                logger.info(f"Retrieved {len(docs)} documents from knowledge base")
            except Exception as kb_err:
                logger.warning(
                    "Bedrock KB retrieve failed (%s), using local knowledge_base_content.md",
                    kb_err,
                )
                docs = _load_local_kb_fallback()
            context_text = format_docs(docs)
            
            # Use chat history directly as plain dicts (no LangChain message conversion)
            # Note: chat_history from memory layer already includes summaries + recent messages
            # The memory layer handles summarization (every 4 messages) and returns:
            # - All summaries (formatted as "[Previous conversation summary (messages X-Y)]: ...")
            # - Last 4 recent messages
            # So we should use ALL chat_history, not limit it further
            if chat_history:
                logger.debug(f"Using {len(chat_history)} messages from chat history (includes summaries from memory layer)")
            
            # Format system prompt
            formatted_system = PRODUCT_DETAIL_SYSTEM_PROMPT.format(
                context=context_text,
                language=language,
                username=username,
                marketplaces_registered=marketplace_info,
                wallet_balance=wallet_info,
                login_location=location_info
            )
            
            # Format messages for Gemini (pass plain dicts directly)
            formatted_messages, _ = format_messages_for_llm(
                chat_messages=chat_history or [],
                system_prompt=formatted_system,
                freeform_text=user_message
            )
            
            # Invoke Gemini
            def invoke_gemini_sync():
                logger.debug("Invoking Gemini for Product Detail category")
                return invoke_gemini_with_tokens(
                    formatted_messages=formatted_messages,
                    system_prompt=formatted_system,
                    max_tokens=1000,
                    temperature=0.1,
                )
            
            logger.info("Invoking Gemini to generate response")
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                current_loop = loop
            response, input_tokens, output_tokens = await current_loop.run_in_executor(
                None,
                invoke_gemini_sync
            )
            logger.info(f"LLM response received (length: {len(response)} characters, input_tokens: {input_tokens}, output_tokens: {output_tokens})")
            
            # Extract structured data from response
            structured = parse_structured_response(response)
            
            # Clean response text (remove JSON blocks)
            clean_reply = clean_response_text(response, structured)
            
            # Return structured response
            result = {
                'reply': clean_reply,
                'intent': structured.get('intent', 'general_query') if structured else 'general_query',
                'agentId': structured.get('agentId') if structured and structured.get('agentId') else None,
                'raw_response': response,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'category': self.category_id
            }
            logger.info(f"Product Detail category processed query - intent: {result['intent']}, agentId: {result['agentId']}")
            return result
            
        except Exception as e:
            logger.error(f"Error in ProductDetailCategory.process_query: {e}", exc_info=True)
            raise Exception(f"Error processing product detail query: {str(e)}")

