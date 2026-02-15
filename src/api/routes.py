from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import uuid
import time
from datetime import datetime
import os
import sys
# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from utils.logger_config import get_logger

# Import new models and services
from src.core.models import (
    SendMessageRequest,
    SendMessageResponse,
    create_success_response,
    create_error_response,
    MessageMetadata,
    ErrorCode,
    IntentType,
    MessageComponents,
    QuickAction,
    ActionType
)
from src.core.backend import my_chatbot_async, modelID
# Wallet service no longer needed - balance comes from request payload
# from src.services.wallet_service import WalletMicroserviceClient
from src.services.agent_service import AgentService
from src.services.intent_extractor import IntentExtractor
from src.services.currency_service import CurrencyService
# Database services
from database import get_conversation_storage
# Memory management
from src.core.memory_layer import get_memory_layer

# Initialize logger
logger = get_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="MySellerCentral Chatbot API",
    description="API for MySellerCentral Assistant Chatbot with optimized response structure",
    version="2.0.0"
)

# Configure CORS - Allow frontend to access the API
# Development: Allow all origins for local development
# Production: Replace with specific frontend domain(s)
import os
is_production = os.getenv("ENVIRONMENT", "development") == "production"

if is_production:
    # Production CORS - allow Streamlit Cloud and common hosting platforms
    allowed_origins = [
        "https://*.streamlit.app",  # Streamlit Community Cloud
        "https://*.onrender.com",   # Render frontends
        "https://*.railway.app",    # Railway frontends
        "https://*.fly.dev",        # Fly.io frontends
    ]
else:
    # Development CORS - allow common localhost ports
    # Use ["*"] for maximum flexibility during development
    allowed_origins = ["*"]  # Allows all origins in development

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
logger.info("Initializing API services")
# Wallet service no longer needed - balance comes from request payload
# wallet_service = WalletMicroserviceClient()
agent_service = AgentService()
intent_extractor = IntentExtractor(agent_service=agent_service)
# Initialize conversation storage service
try:
    conversation_storage = get_conversation_storage()
    logger.info("Conversation storage service initialized successfully")
except Exception as e:
    logger.warning(f"Conversation storage service initialization failed: {e}. Messages will not be persisted.")
    conversation_storage = None
logger.info(f"API services initialized successfully. Using model: {modelID}")

# Legacy models for backward compatibility
class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    language: Optional[str] = "English"
    chat_history: Optional[List[Message]] = []

class ChatResponse(BaseModel):
    response: str
    status: str = "success"

# Health check endpoint
@app.get("/")
def root():
    logger.info("Root endpoint accessed")
    return {
        "status": "ok",
        "message": "MySellerCentral Chatbot API is running",
        "version": "2.0.0",
        "endpoints": {
            "sendMessage": "/api/chat/message",
            "getConversationMessages": "/api/chat/conversation/{conversation_id}/messages",
            "openConversation": "/api/chat/conversation/{conversation_id}/open",
            "getUserConversations": "/api/user/{user_id}/conversations",
            "legacyChat": "/api/chat",
            "health": "/health"
        }
    }

@app.get("/health")
def health_check():
    logger.debug("Health check endpoint accessed")
    return {"status": "healthy"}

# New optimized endpoint
@app.post("/api/chat/message", response_model=SendMessageResponse)
async def send_message(request: SendMessageRequest):
    """
    Optimized chat endpoint with structured response and error handling.
    
    Request body:
    - message: User's message (required)
    - conversationId: Conversation identifier (required)
    - messageType: Type of message (optional, default: "text")
    - context: Context information including userId and clientInfo (required)
    - language: Response language (optional, default: "English")
    
    Returns:
    - Standardized response with success/error structure
    - Structured components for rich UI rendering
    - Wallet balance information
    - Response metadata
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()
    logger.info(f"Received send_message request - request_id: {request_id}, user_id: {request.context.userId}, message: {request.message[:100]}...")
    
    try:
        # 0. Get or create conversation (handle new conversations)
        conversation_id = request.conversationId
        if conversation_storage:
            try:
                # Treat empty string or "new" as a new conversation
                if not conversation_id or conversation_id.strip() == "" or conversation_id.lower() == "new":
                    conversation_id = None  # Will trigger creation of new conversation
                
                # Convert clientInfo to dict for storage
                client_info_dict = None
                if request.context.clientInfo:
                    client_info_dict = {
                        "device": request.context.clientInfo.device,
                        "appVersion": request.context.clientInfo.appVersion,
                        "timezone": request.context.clientInfo.timezone,
                        "platform": request.context.clientInfo.platform,
                        "userAgent": request.context.clientInfo.userAgent,
                        "country": request.context.clientInfo.country
                    }
                
                conversation_id = await conversation_storage.get_or_create_conversation(
                    user_id=request.context.userId,
                    conversation_id=conversation_id,
                    client_info=client_info_dict
                )
                logger.info(f"Using conversation: {conversation_id} for user: {request.context.userId}")
            except Exception as e:
                logger.error(f"Error managing conversation: {e}", exc_info=True)
                # Continue without conversation storage if it fails
        else:
            logger.debug("Conversation storage not available, using provided conversationId")
        
        # 1. Get wallet balance from request context (frontend provides it)
        wallet_balance = request.context.wallet_balance if request.context.wallet_balance is not None else 0.0
        logger.info(f"Wallet balance from request context: {wallet_balance} for user: {request.context.userId}")
        
        # 1.5. Save user message to database
        if conversation_storage and conversation_id:
            try:
                user_message_id = await conversation_storage.save_user_message(
                    conversation_id=conversation_id,
                    user_id=request.context.userId,
                    content=request.message,
                    message_type=request.messageType.value if hasattr(request.messageType, 'value') else str(request.messageType)
                )
                if user_message_id:
                    logger.debug(f"Saved user message: {user_message_id}")
            except Exception as e:
                logger.warning(f"Failed to save user message: {e}", exc_info=True)
                # Continue even if saving fails
        
        # 2. Process message with LLM
        try:
            # Get chat history using memory layer (handles summarization automatically)
            chat_history = []
            if conversation_id:
                try:
                    memory_layer = get_memory_layer()
                    chat_history = await memory_layer.get_formatted_chat_history_for_backend(conversation_id)
                    logger.debug(f"Retrieved chat history for conversation {conversation_id}: {len(chat_history)} messages (includes summary if applicable)")
                except Exception as e:
                    logger.warning(f"Failed to retrieve chat history from memory layer: {e}", exc_info=True)
                    # Continue with empty chat history if memory layer fails
                    chat_history = []
            
            logger.debug(f"Processing message with LLM - language: {request.language}, conversation_id: {conversation_id}")
            
            # TODO: Get username from microservice - for now using constant
            username = request.context.username if request.context.username else ""
            logger.debug(f"Using username for LLM: {username}")
            
            # Prepare additional context to pass to backend
            additional_context = {
                "userId": request.context.userId,
                "marketplaces_registered": request.context.marketplaces_registered if request.context.marketplaces_registered else [],
                "walletBalance": wallet_balance,
                "wallet_balance": wallet_balance,
                "loginLocation": request.context.loginLocation,
                "login_location": request.context.loginLocation,
                "language": request.language,
                "username": username
            }
            logger.debug(f"Prepared context with marketplaces_registered: {additional_context.get('marketplaces_registered')}, walletBalance: {wallet_balance}, loginLocation: {request.context.loginLocation}")
            
            llm_result = await my_chatbot_async(
                language=request.language,
                freeform_text=request.message,
                chat_history=chat_history if chat_history else None,
                username=username,
                context=additional_context
            )
            logger.info("LLM response received successfully")
        except Exception as e:
            logger.error(f"Error processing message with LLM: {e}", exc_info=True)
            return create_error_response(
                error_code=ErrorCode.MODEL_ERROR,
                error_message="Failed to generate response from AI model",
                details={"error": str(e)},
                wallet_balance=wallet_balance
            )
        
        # 3. Detect currency from user location (loginLocation is primary source)
        # This is done early so it's available for error messages and components
        user_currency = CurrencyService.detect_currency(
            login_location=request.context.loginLocation,
            country=request.context.clientInfo.country,
            timezone=request.context.clientInfo.timezone
        )
        logger.info(f"Detected currency: {user_currency} for user: {request.context.userId} (loginLocation: {request.context.loginLocation}, country: {request.context.clientInfo.country}, timezone: {request.context.clientInfo.timezone})")
        
        # 4. Extract intent and agent from structured response
        # Handle both new structured format (dict) and legacy format (str)
        # Also extract token counts
        input_tokens = None
        output_tokens = None
        response_intent = None  # This will be used in the response (orchestrator category)
        component_intent = None  # This will be used for component generation (LLM's original intent)
        try:
            logger.debug("Extracting intent and agent from LLM response")
            if isinstance(llm_result, dict):
                logger.debug("Processing structured format (dict) from LLM")
                
                # Get the user query intent (category classification) from orchestrator
                # This is the category classification: product_detail or analytics_reporting
                # The orchestrator classifies queries into these categories using LLM
                query_category = llm_result.get('category')
                
                # Get the LLM's original intent (from category handler) for component generation
                # This is what the category handler detected (e.g., agent_suggestion, pricing_query, etc.)
                llm_original_intent = llm_result.get('intent', 'general_query')
                
                llm_reply = llm_result.get('reply', '')
                # Extract token counts if available
                input_tokens = llm_result.get('input_tokens')
                output_tokens = llm_result.get('output_tokens')
                # Extract all agents from LLM's agentId (could be list or string)
                llm_agent_ids = llm_result.get('agentId')
                
                # Categories that require agent data: only product_detail and ai_content_generation
                # All other categories should skip agent extraction and KB access
                AGENT_REQUIRED_CATEGORIES = ['product_detail', 'ai_content_generation']
                
                # OPTIMIZATION: Fetch agent_db ONCE at the start for agent-required categories
                # This avoids multiple calls to get_agent_database() during request processing
                agent_db = None
                if query_category in AGENT_REQUIRED_CATEGORIES:
                    agent_db = intent_extractor.get_agent_database(cache_only=True)
                    logger.info(f"✅ OPTIMIZATION: Fetched agent_db ONCE for request ({len(agent_db)} agents) - will be reused throughout request processing")
                
                # Skip agent extraction for categories that don't need agents
                if query_category not in AGENT_REQUIRED_CATEGORIES:
                    logger.debug(f"Skipping agent extraction for {query_category} query (not needed - only product_detail and ai_content_generation require agents)")
                    agent_id = None
                    extracted_intent = None
                    component_intent = llm_original_intent
                    response_intent = str(query_category) if query_category else query_category
                    llm_agent_ids = [] if not llm_agent_ids else llm_agent_ids
                    logger.info(f"Response intent (orchestrator category): {response_intent}, Component intent (LLM original): {component_intent}, agent_id: {agent_id}")
                else:
                    # Extract agent information only for categories that need agents
                    # Pass pre-fetched agent_db to avoid repeated calls
                    extracted_intent, agent_id = intent_extractor.extract_intent(request.message, llm_result, agent_db=agent_db)
                    
                    # Use LLM's original intent for component generation (so agent cards work)
                    component_intent = llm_original_intent if llm_original_intent else extracted_intent
                    
                    # Use orchestrator's category for the response intent field
                    if query_category:
                        response_intent = str(query_category)  # This goes in the response
                        logger.info(f"Response intent (orchestrator category): {response_intent}, Component intent (LLM original): {component_intent}, agent_id: {agent_id}")
                    else:
                        # Fallback: use extracted intent for both
                        response_intent = extracted_intent if isinstance(extracted_intent, str) else str(extracted_intent)
                        component_intent = extracted_intent
                        logger.warning(f"Category not found in orchestrator result, using extracted intent for both: {response_intent}")
                    
                    # Filter agent IDs using pre-fetched agent database (only for agent-required categories)
                    if isinstance(llm_agent_ids, list):
                        # Filter to only valid agents
                        llm_agent_ids = [a for a in llm_agent_ids if isinstance(a, str) and a in agent_db]
                        logger.debug(f"Filtered LLM agent IDs: {llm_agent_ids}")
                    elif isinstance(llm_agent_ids, str) and llm_agent_ids in agent_db:
                        llm_agent_ids = [llm_agent_ids]
                        logger.debug(f"Single LLM agent ID: {llm_agent_ids}")
                    else:
                        llm_agent_ids = []
                        logger.debug("No valid LLM agent IDs found")
            else:
                # Legacy format: string response
                logger.debug("Processing legacy format (string) from LLM")
                # For legacy format, we don't have query_category, so we need to extract intent
                # Fetch agent_db once to avoid repeated calls during extraction
                agent_db = intent_extractor.get_agent_database(cache_only=True)
                logger.info(f"✅ OPTIMIZATION: Fetched agent_db ONCE for legacy format request ({len(agent_db)} agents) - will be reused throughout request processing")
                extracted_intent, agent_id = intent_extractor.extract_intent(request.message, llm_result, agent_db=agent_db)
                component_intent = extracted_intent
                response_intent = extracted_intent if isinstance(extracted_intent, str) else str(extracted_intent)
                llm_reply = llm_result
                llm_agent_ids = []
                query_category = None  # Legacy format doesn't have category
            
            logger.info(f"Response intent: {response_intent}, Component intent: {component_intent}, agent_id: {agent_id}, tokens: {input_tokens} in / {output_tokens} out")
            
            # Extract analytics data from LLM result if available (for analytics_reporting category)
            analytics_data = None
            if isinstance(llm_result, dict):
                analytics_data = llm_result.get('analytics_data')
                if analytics_data:
                    logger.info(f"Extracted analytics data from LLM result - includes visualization: {bool(analytics_data.get('visualization'))}, SQL: {bool(analytics_data.get('generated_sql'))}, table_data: {bool(analytics_data.get('table_data'))}")
            
            # 5. Generate components - ASIN validation failed: show client ASINs as quick-action buttons
            if isinstance(llm_result, dict) and llm_result.get('intent') == 'asin_validation_failed':
                client_asins = llm_result.get('client_asins') or []
                if client_asins:
                    asin_buttons = [
                        QuickAction(
                            label=asin,
                            message=f"Show me insights for ASIN {asin}",
                            actionType=ActionType.MESSAGE,
                        )
                        for asin in client_asins[:50]  # cap at 50 buttons
                    ]
                    components = MessageComponents(quickActions=asin_buttons)
                    logger.info(f"Built ASIN selection components: {len(asin_buttons)} quick actions")
                else:
                    components = None
            elif isinstance(llm_result, dict):
                components = None
            else:
                components = None
            
            # 5b. Generate components - only for categories that might need agent cards (skip if already set e.g. ASIN buttons)
            if components is None:
                # Skip component generation for categories that don't need agents
                AGENT_REQUIRED_CATEGORIES = ['product_detail', 'ai_content_generation']
                # For legacy format (query_category is None), only generate components if intent suggests agent
                if query_category in AGENT_REQUIRED_CATEGORIES or (query_category is None and component_intent == IntentType.AGENT_SUGGESTION):
                    # Generate components - use component_intent (LLM's original intent) for component generation
                    # This ensures agent cards are generated when LLM detects agent_suggestion
                    # Pass pre-fetched agent_db to avoid repeated calls
                    # If agent_db wasn't fetched yet (legacy format without agent requirement), fetch it now
                    if agent_db is None:
                        agent_db = intent_extractor.get_agent_database(cache_only=True)
                        logger.info(f"✅ OPTIMIZATION: Fetched agent_db for component generation ({len(agent_db)} agents) - will be reused")
                    components = intent_extractor.generate_components(
                        intent=component_intent,  # Use LLM's original intent for component generation
                        llm_response=llm_reply,
                        wallet_balance=wallet_balance,
                        user_message=request.message,
                        agent_id=agent_id,  # Pass pre-extracted agent_id if available
                        llm_agent_ids=llm_agent_ids,  # Pass all agents from LLM response
                        currency=user_currency,  # Pass detected currency
                        country=request.context.clientInfo.country,  # Pass country for reference
                        timezone=request.context.clientInfo.timezone,  # Pass timezone for reference
                        cache_only=True,  # Use cache only for agent cards, no KB query
                        agent_db=agent_db,  # Pass pre-fetched agent_db to avoid repeated calls
                        query_category=query_category,  # product_detail → agent cards from reply content only
                    )
                    # Add analytics data to components if available (even for agent categories)
                    if analytics_data and components:
                        components.analyticsData = analytics_data
                        logger.info("Added analytics data to existing components")
                else:
                    # For analytics_reporting category, create components with analytics data
                    if query_category == 'analytics_reporting' and analytics_data:
                        logger.info("Creating components for analytics_reporting category with analytics data")
                        components = MessageComponents(analyticsData=analytics_data)
                    else:
                        # No components needed for non-agent categories
                        logger.debug(f"Skipping component generation for {query_category} (not an agent-required category)")
                        components = None
            if components:
                logger.info("Components generated successfully")
            else:
                logger.debug("No components generated")
        except Exception as e:
            # If intent extraction fails, log and continue without components
            logger.error(f"Error in intent extraction: {str(e)}", exc_info=True)
            if not response_intent:
                response_intent = IntentType.GENERAL_QUERY.value if hasattr(IntentType.GENERAL_QUERY, 'value') else str(IntentType.GENERAL_QUERY)
            component_intent = IntentType.GENERAL_QUERY
            components = None
            llm_reply = llm_result if isinstance(llm_result, str) else llm_result.get('reply', '') if isinstance(llm_result, dict) else str(llm_result)
        
        # 6. Check wallet balance for agent suggestions
        # Skip wallet validation for product_detail and ai_content_generation categories
        # These categories should show the agent card regardless of balance
        # Wallet validation will happen when user clicks the launch button (handled by frontend)
        skip_wallet_check = response_intent and response_intent in ['product_detail', 'ai_content_generation']
        
        if components and components.agentCard and not skip_wallet_check:
            required_amount = components.agentCard.cost
            logger.debug(f"Checking wallet balance for agent - required: {required_amount}")
            current_balance = wallet_balance
            has_sufficient = current_balance >= required_amount
            
            if not has_sufficient:
                logger.warning(f"Insufficient balance for user {request.context.userId} - required: {required_amount}, current: {current_balance}")
                # Format amount with currency symbol (₹ for INR, $ for USD)
                formatted_amount = CurrencyService.format_currency(required_amount, user_currency)
                
                # Create quick action button for top-up
                topup_quick_action = QuickAction(
                    label="Click here to Top-up",
                    url="https://mysellercentral.com/ai-agents/",
                    actionType=ActionType.URL,
                    icon=None
                )
                
                # Create components with quick action
                error_components = MessageComponents(
                    quickActions=[topup_quick_action]
                )
                
                return create_error_response(
                    error_code=ErrorCode.INSUFFICIENT_BALANCE,
                    error_message=f"Insufficient balance {username}. You need {formatted_amount} to use this agent.",
                    details={
                        "required": required_amount,
                        "current": current_balance,
                        "shortfall": required_amount - current_balance
                    },
                    wallet_balance=current_balance,
                    components=error_components
                )
            logger.info(f"Wallet balance sufficient for agent - required: {required_amount}, current: {current_balance}")
        elif components and components.agentCard and skip_wallet_check:
            logger.info(f"Skipping wallet balance check for category: {response_intent}. Agent card will be shown regardless of balance. Validation will occur when user clicks launch button.")
        
        # 7. Calculate latency
        latency_ms = (time.time() - start_time) * 1000
        logger.info(f"Request processed in {latency_ms:.2f}ms")
        
        # 8. Generate message ID
        message_id = f"msg_{uuid.uuid4().hex[:12]}"
        logger.debug(f"Generated message_id: {message_id}")
        
        # 8.5. Create metadata with token counts
        total_tokens = (input_tokens + output_tokens) if (input_tokens is not None and output_tokens is not None) else None
        metadata = MessageMetadata(
            modelVersion=f"{modelID}",
            latencyMs=round(latency_ms, 2),
            requestId=request_id,
            inputTokens=input_tokens,
            outputTokens=output_tokens,
            tokensUsed=total_tokens
        )
        
        # 8.6. Save assistant message to database
        notice = llm_result.get('notice') if isinstance(llm_result, dict) else None
        if conversation_storage and conversation_id:
            try:
                # Build assistant response data structures
                assistant_response = {
                    "intent": response_intent if response_intent else (component_intent.value if hasattr(component_intent, 'value') else str(component_intent))
                }
                
                # Convert components to dict format for storage
                agent_card_dict = None
                suggested_agents_list = None
                quick_actions_list = None
                analytics_data_dict = None

                if components:
                    if components.agentCard:
                        agent_card_dict = {
                            "agentId": components.agentCard.agentId,
                            "name": components.agentCard.name,
                            "icon": components.agentCard.icon,
                            "cost": components.agentCard.cost,
                            "currency": components.agentCard.currency,
                            "currencySymbol": components.agentCard.currencySymbol,
                            "walletAfter": components.agentCard.walletAfter,
                            "features": components.agentCard.features,
                            "action": components.agentCard.action,
                            "marketplace": components.agentCard.marketplace,
                            "description": components.agentCard.description
                        }
                        if components.agentCard.quickActions:
                            agent_card_dict["quickActions"] = [
                                {
                                    "label": qa.label,
                                    "message": qa.message,
                                    "url": qa.url,
                                    "actionType": qa.actionType.value if hasattr(qa.actionType, 'value') else str(qa.actionType),
                                    "icon": qa.icon
                                }
                                for qa in components.agentCard.quickActions
                            ]
                    
                    if components.suggestedAgents:
                        suggested_agents_list = [
                            {
                                "agentId": agent.agentId,
                                "name": agent.name,
                                "icon": agent.icon,
                                "cost": agent.cost,
                                "currency": agent.currency,
                                "currencySymbol": agent.currencySymbol,
                                "walletAfter": agent.walletAfter,
                                "features": agent.features,
                                "action": agent.action,
                                "marketplace": agent.marketplace,
                                "description": agent.description
                            }
                            for agent in components.suggestedAgents
                        ]
                    
                    if components.quickActions:
                        quick_actions_list = [
                            {
                                "label": qa.label,
                                "message": qa.message,
                                "url": qa.url,
                                "actionType": qa.actionType.value if hasattr(qa.actionType, 'value') else str(qa.actionType),
                                "icon": qa.icon
                            }
                            for qa in components.quickActions
                        ]
                    if components.analyticsData:
                        analytics_data_dict = components.analyticsData

                # Build processing metadata
                processing_dict = {
                    "modelVersion": metadata.modelVersion,
                    "latencyMs": metadata.latencyMs,
                    "requestId": metadata.requestId
                }
                if metadata.tokensUsed is not None:
                    processing_dict["tokensUsed"] = metadata.tokensUsed
                if metadata.inputTokens is not None:
                    processing_dict["inputTokens"] = metadata.inputTokens
                if metadata.outputTokens is not None:
                    processing_dict["outputTokens"] = metadata.outputTokens
                if metadata.knowledgeBaseHits is not None:
                    processing_dict["knowledgeBaseHits"] = metadata.knowledgeBaseHits
                
                assistant_message_id = await conversation_storage.save_assistant_message(
                    conversation_id=conversation_id,
                    user_id=request.context.userId,
                    content=llm_reply,
                    intent=assistant_response["intent"],
                    assistant_response=assistant_response,
                    agent_card=agent_card_dict,
                    suggested_agents=suggested_agents_list,
                    quick_actions=quick_actions_list,
                    analytics_data=analytics_data_dict,
                    processing=processing_dict,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    notice=notice
                )
                if assistant_message_id:
                    logger.debug(f"Saved assistant message: {assistant_message_id}")
            except Exception as e:
                logger.warning(f"Failed to save assistant message: {e}", exc_info=True)
                # Continue even if saving fails
        
        # 9. Return success response (use the conversation_id from storage)
        # Use response_intent (orchestrator category) for the response intent field
        final_intent = response_intent if response_intent else (component_intent.value if hasattr(component_intent, 'value') else str(component_intent))
        logger.info(f"Returning success response for request_id: {request_id} with intent: {final_intent}")

        # Extract original and enriched messages from orchestrator result (if available)
        # These represent:
        # - originalMessage: raw user query received by the API
        # - enrichedMessage: final enriched query after user_intent + marketplace/work_status validation
        original_message = None
        enriched_message = None
        if isinstance(llm_result, dict):
            original_message = llm_result.get('original_message')
            enriched_message = llm_result.get('enriched_message')
        # Fallbacks if orchestrator did not provide them (e.g., legacy/edge cases)
        if original_message is None:
            original_message = request.message

        return create_success_response(
            message_id=message_id,
            reply=llm_reply,
            intent=final_intent,  # Use orchestrator category for response intent
            conversation_id=conversation_id if conversation_id else request.conversationId,
            wallet_balance=wallet_balance,
            components=components,
            message_type=request.messageType,
            metadata=metadata,
            notice=notice,
            original_message=original_message,
            enriched_message=enriched_message,
        )
    
    except Exception as e:
        # Catch any unexpected errors
        logger.error(f"Unexpected error in send_message endpoint: {e}", exc_info=True)
        return create_error_response(
            error_code=ErrorCode.INTERNAL_ERROR,
            error_message="An unexpected error occurred",
            details={"error": str(e), "requestId": request_id}
        )

# Get messages by conversationId
@app.get("/api/chat/conversation/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: str):
    """
    Retrieve all messages for a conversation.
    @app
    Args:
        conversation_id: Conversation identifier
        
    Returns:
        List of messages for the conversation
    """
    request_id = str(uuid.uuid4())
    logger.info(f"Received get messages request - request_id: {request_id}, conversation_id: {conversation_id}")
    
    try:
        if not conversation_storage:
            logger.error("Conversation storage service not available")
            raise HTTPException(
                status_code=503,
                detail="Conversation storage service not available"
            )
        
        # Get messages from database
        messages = await conversation_storage.get_conversation_messages(conversation_id)
        
        # Also get conversation details
        conversation = None
        try:
            from database import get_conversations_service
            conv_service = get_conversations_service()
            conversation = await conv_service.get_conversation(conversation_id)
        except Exception as e:
            logger.warning(f"Failed to get conversation details: {e}")
        
        logger.info(f"Retrieved {len(messages)} messages for conversation: {conversation_id}")
        
        return {
            "success": True,
            "data": {
                "conversationId": conversation_id,
                "conversation": conversation,
                "messages": messages,
                "messageCount": len(messages)
            },
            "requestId": request_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving messages: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving messages: {str(e)}"
        )

# Open conversation by conversationId (for sidebar click)
@app.get("/api/chat/conversation/{conversation_id}")
async def open_conversation(conversation_id: str):
    """
    Open a conversation by conversationId. This endpoint is designed for when
    a user clicks on a conversation from the sidebar to view its history.
    Works independently of user_id - only requires conversation_id.
    
    Args:
        conversation_id: Conversation identifier
        
    Returns:
        Conversation details with all messages ready for display
    """
    request_id = str(uuid.uuid4())
    logger.info(f"Received open conversation request - request_id: {request_id}, conversation_id: {conversation_id}")
    
    try:
        # Try to get conversation storage, attempt re-initialization if None
        storage_service = conversation_storage
        if not storage_service:
            logger.warning("Conversation storage not initialized, attempting to initialize...")
            try:
                from database import get_conversation_storage
                storage_service = get_conversation_storage()
                logger.info("Successfully initialized conversation storage on-demand")
            except Exception as e:
                logger.error(f"Failed to initialize conversation storage: {e}", exc_info=True)
                raise HTTPException(
                    status_code=503,
                    detail=f"Conversation storage service not available. Please ensure MongoDB is running and MONGODB_URI is configured. Error: {str(e)}"
                )
        
        # Get conversation details
        conversation = None
        try:
            from database import get_conversations_service
            conv_service = get_conversations_service()
            conversation = await conv_service.get_conversation(conversation_id)
            
            if not conversation:
                logger.warning(f"Conversation not found: {conversation_id}")
                raise HTTPException(
                    status_code=404,
                    detail=f"Conversation not found: {conversation_id}"
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get conversation details: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Error retrieving conversation: {str(e)}"
            )
        
        # Get all messages for this conversation
        messages = await storage_service.get_conversation_messages(conversation_id)
        logger.info(f"Retrieved {len(messages)} messages for conversation: {conversation_id}")
        
        # Format conversation data
        conversation_data = {
            "conversationId": conversation.get("_id"),
            "userId": conversation.get("userId"),
            "status": conversation.get("status"),
            "title": conversation.get("title"),
            "createdAt": conversation.get("createdAt").isoformat() if conversation.get("createdAt") else None,
            "updatedAt": conversation.get("updatedAt").isoformat() if conversation.get("updatedAt") else None,
            "lastMessageAt": conversation.get("lastMessageAt").isoformat() if conversation.get("lastMessageAt") else None,
            "stats": conversation.get("stats"),
            "clientInfo": conversation.get("clientInfo")
        }
        
        return {
            "success": True,
            "data": {
                "conversation": conversation_data,
                "messages": messages,
                "messageCount": len(messages)
            },
            "requestId": request_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error opening conversation: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error opening conversation: {str(e)}"
        )

# Get all conversations and messages for a user
@app.get("/api/user/{user_id}/conversations")
async def get_user_conversations(user_id: str, include_messages: bool = True, limit: int = 50, skip: int = 0):
    """
    Retrieve all conversations and their messages for a user.
    
    Args:
        user_id: User identifier
        include_messages: Whether to include messages for each conversation (default: True)
        limit: Maximum number of conversations to return (default: 50)
        skip: Number of conversations to skip for pagination (default: 0)
        
    Returns:
        List of conversations with their messages
    """
    request_id = str(uuid.uuid4())
    logger.info(f"Received get user conversations request - request_id: {request_id}, user_id: {user_id}")
    
    try:
        if not conversation_storage:
            logger.error("Conversation storage service not available")
            raise HTTPException(
                status_code=503,
                detail="Conversation storage service not available"
            )
        
        # Get conversations service
        from database import get_conversations_service
        conv_service = get_conversations_service()
        
        # Get all conversations for the user
        conversations = await conv_service.get_user_conversations(
            user_id=user_id,
            limit=limit,
            skip=skip
        )
        
        logger.info(f"Retrieved {len(conversations)} conversations for user: {user_id}")
        
        # If include_messages is True, fetch messages for each conversation
        conversations_with_messages = []
        for conv in conversations:
            conv_data = {
                "conversationId": conv.get("_id"),
                "userId": conv.get("userId"),
                "status": conv.get("status"),
                "title": conv.get("title"),
                "createdAt": conv.get("createdAt").isoformat() if conv.get("createdAt") else None,
                "updatedAt": conv.get("updatedAt").isoformat() if conv.get("updatedAt") else None,
                "lastMessageAt": conv.get("lastMessageAt").isoformat() if conv.get("lastMessageAt") else None,
                "stats": conv.get("stats"),
                "clientInfo": conv.get("clientInfo")
            }
            
            if include_messages:
                # Get messages for this conversation
                messages = await conversation_storage.get_conversation_messages(
                    conversation_id=conv.get("_id"),
                    limit=100  # Limit messages per conversation
                )
                conv_data["messages"] = messages
                conv_data["messageCount"] = len(messages)
            
            conversations_with_messages.append(conv_data)
        
        return {
            "success": True,
            "data": {
                "userId": user_id,
                "conversations": conversations_with_messages,
                "totalConversations": len(conversations_with_messages)
            },
            "requestId": request_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving user conversations: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving user conversations: {str(e)}"
        )


# Legacy endpoint for backward compatibility
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Legacy chat endpoint for backward compatibility.
    
    Request body:
    - message: User's message (required)
    - language: Language for response (optional, default: "English")
    - chat_history: Previous conversation messages (optional)
    
    Returns:
    - response: AI assistant's response
    - status: Request status
    """
    logger.info(f"Received legacy chat request - message: {request.message[:100]}..., language: {request.language}")
    try:
        # Convert Pydantic models to format expected by backend
        chat_history = []
        if request.chat_history:
            chat_history = [
                {"role": msg.role, "content": msg.content}
                for msg in request.chat_history
            ]
            logger.debug(f"Converted {len(chat_history)} messages from chat history")
        
        # Call the chatbot function
        logger.debug("Calling my_chatbot_async for legacy endpoint")
        llm_result = await my_chatbot_async(
            language=request.language,
            freeform_text=request.message,
            chat_history=chat_history if chat_history else None
        )
        
        # Handle both structured (dict) and legacy (str) response formats
        if isinstance(llm_result, dict):
            response_text = llm_result.get('reply', '')
            logger.debug("Extracted reply from structured response")
        else:
            response_text = llm_result
            logger.debug("Using string response directly")
        
        logger.info("Legacy chat request processed successfully")
        return ChatResponse(response=response_text, status="success")
    
    except Exception as e:
        logger.error(f"Error processing legacy chat request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing chat request: {str(e)}"
        )

# Run the server
if __name__ == "__main__":
    logger.info("Starting FastAPI server on 0.0.0.0:8502")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8502,
        workers= 5  # For development; increase for production
    )
