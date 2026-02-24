"""
Optimized API Models with Consistent Structure and Error Handling
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class MessageType(str, Enum):
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"


class IntentType(str, Enum):
    AGENT_SUGGESTION = "agent_suggestion"
    PRICING_QUERY = "pricing_query"
    FEATURE_QUERY = "feature_query"
    MARKETPLACE_QUERY = "marketplace_query"
    GENERAL_QUERY = "general_query"
    ONBOARDING = "onboarding"
    SUPPORT = "support"


class ActionType(str, Enum):
    MESSAGE = "message"
    URL = "url"
    DEEP_LINK = "deep_link"
    LAUNCH_AGENT = "launch_agent"


# ============================================================================
# Request Models
# ============================================================================

class ClientInfo(BaseModel):
    """Client device and app information"""
    device: str = Field(..., description="Device type: mobile, desktop, tablet")
    appVersion: str = Field(..., description="Application version")
    timezone: str = Field(..., description="User timezone (e.g., Asia/Kolkata)")
    platform: Optional[str] = Field(None, description="Platform: ios, android, web")
    userAgent: Optional[str] = Field(None, description="User agent string")
    country: Optional[str] = Field(None, description="User country code (e.g., IN, US). If not provided, will be derived from timezone")


class ChatContext(BaseModel):
    """Context information for the chat request"""
    userId: str = Field(..., description="Unique user identifier")
    username: Optional[str] = Field(None, description="User's display name (used for personalization in LLM responses)")
    marketplaces_registered: Optional[List[str]] = Field(default_factory=list, description="List of marketplaces the user is registered on (e.g., ['Amazon', 'Flipkart'])")
    wallet_balance: Optional[float] = Field(None, description="User's current wallet balance")
    previousIntent: Optional[str] = Field(None, description="Previous detected intent")
    loginLocation: Optional[str] = Field(None, description="User's login location (e.g., 'India', 'US', 'Other'). Used to determine currency (INR for India, USD for others)")
    clientInfo: ClientInfo = Field(..., description="Client device information")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class SendMessageRequest(BaseModel):
    """Request model for sending a chat message"""
    message: str = Field(..., min_length=1, description="User's message (used for processing)")
    conversationId: str = Field(..., description="Conversation identifier")
    messageType: MessageType = Field(default=MessageType.TEXT, description="Type of message")
    context: ChatContext = Field(..., description="Request context")
    language: Optional[str] = Field(default="English", description="Response language")
    displayContent: Optional[str] = Field(None, description="Optional user-facing text to store/display instead of message (e.g. from quick action displayMessage)")


# ============================================================================
# Response Component Models
# ============================================================================

class AgentCard(BaseModel):
    """Agent suggestion card component"""
    agentId: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Agent display name")
    icon: str = Field(..., description="Agent icon/emoji")
    cost: float = Field(..., ge=0, description="Cost in tokens/currency (converted based on user location)")
    currency: str = Field(default="INR", description="Currency code (INR or USD)")
    currencySymbol: str = Field(default="₹", description="Currency symbol (₹ or $)")
    walletAfter: float = Field(..., ge=0, description="Projected wallet balance after using agent")
    features: List[str] = Field(default_factory=list, description="Key features of the agent")
    action: str = Field(default="launch_agent", description="Action to take")
    marketplace: Optional[List[str]] = Field(default_factory=list, description="Supported marketplaces")
    description: Optional[str] = Field(None, description="Agent description")
    quickActions: Optional[List['QuickAction']] = Field(default_factory=list, description="Quick action buttons for this agent")


class QuickAction(BaseModel):
    """Quick action button component"""
    label: str = Field(..., description="Button label")
    message: Optional[str] = Field(None, description="Message to send when clicked (used for backend processing)")
    displayMessage: Optional[str] = Field(None, description="User-facing text to show in chat; when sent as displayContent, backend stores this instead of message")
    url: Optional[str] = Field(None, description="URL to navigate to")
    actionType: ActionType = Field(default=ActionType.MESSAGE, description="Type of action")
    icon: Optional[str] = Field(None, description="Optional icon for the action")


class CategoryMapperCard(BaseModel):
    """Category mapper card (marketplace + category paths); no pricing/agent fields."""
    name: str = Field(..., description="Marketplace display name")
    features: List[str] = Field(default_factory=list, description="Key features (e.g. category count)")
    action: str = Field(default="message", description="Action to take")
    marketplace: Optional[List[str]] = Field(default_factory=list, description="Marketplace ids (e.g. amazon.in)")
    description: Optional[str] = Field(None, description="Card description")
    quickActions: Optional[List[QuickAction]] = Field(default_factory=list, description="Quick action buttons for category paths")


class MessageComponents(BaseModel):
    """Structured components for rich UI rendering"""
    agentCard: Optional[AgentCard] = Field(None, description="Primary agent suggestion")
    suggestedAgents: Optional[List[AgentCard]] = Field(default_factory=list, description="Alternative agent suggestions")
    quickActions: Optional[List[QuickAction]] = Field(default_factory=list, description="Quick action buttons")
    categoryMapperCards: Optional[List[CategoryMapperCard]] = Field(default_factory=list, description="Category mapper cards for insights_kb (marketplace cards with category paths)")
    pricingInfo: Optional[Dict[str, Any]] = Field(None, description="Pricing information if pricing query")
    marketplaceInfo: Optional[Dict[str, Any]] = Field(None, description="Marketplace information if marketplace query")
    analyticsData: Optional[Dict[str, Any]] = Field(None, description="Analytics data including visualization, SQL, table data, etc.")


class MessageMetadata(BaseModel):
    """Metadata about the response generation"""
    modelVersion: str = Field(..., description="Model version used")
    tokensUsed: Optional[int] = Field(None, ge=0, description="Total tokens consumed (input + output)")
    inputTokens: Optional[int] = Field(None, ge=0, description="Input tokens consumed")
    outputTokens: Optional[int] = Field(None, ge=0, description="Output tokens consumed")
    latencyMs: Optional[float] = Field(None, ge=0, description="Response latency in milliseconds")
    knowledgeBaseHits: Optional[int] = Field(None, ge=0, description="Number of knowledge base documents retrieved")
    requestId: Optional[str] = Field(None, description="Request ID for tracing")


# ============================================================================
# Response Models
# ============================================================================

class MessageData(BaseModel):
    """Main message response data"""
    messageId: str = Field(..., description="Unique message identifier")
    reply: str = Field(..., description="AI assistant's reply")
    intent: str = Field(..., description="Detected intent")
    originalMessage: Optional[str] = Field(None, description="Original user message as received by the API")
    enrichedMessage: Optional[str] = Field(None, description="Final enriched query after intent detection and validations (used for routing)")
    conversationId: str = Field(..., description="Conversation identifier")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    messageType: MessageType = Field(default=MessageType.TEXT, description="Message type")
    components: Optional[MessageComponents] = Field(None, description="Structured UI components")
    walletBalance: float = Field(..., ge=0, description="Current wallet balance (server-validated)")
    notice: Optional[str] = Field(None, description="Status message e.g. from marketplace validator (not the main reply)")


class ErrorDetail(BaseModel):
    """Standardized error detail structure"""
    code: str = Field(..., description="Error code (e.g., INSUFFICIENT_BALANCE)")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    walletBalance: Optional[float] = Field(None, ge=0, description="Current wallet balance if relevant")
    components: Optional[MessageComponents] = Field(None, description="Structured UI components for error responses (e.g., quick actions)")


class SendMessageResponse(BaseModel):
    """Standardized API response structure"""
    success: bool = Field(..., description="Whether the request was successful")
    data: Optional[MessageData] = Field(None, description="Response data (present if success=true)")
    error: Optional[ErrorDetail] = Field(None, description="Error details (present if success=false)")
    metadata: Optional[MessageMetadata] = Field(None, description="Response metadata")


# ============================================================================
# Error Codes
# ============================================================================

class ErrorCode:
    """Standard error codes"""
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    AGENT_UNAVAILABLE = "AGENT_UNAVAILABLE"
    INVALID_CONVERSATION = "INVALID_CONVERSATION"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    KNOWLEDGE_BASE_ERROR = "KNOWLEDGE_BASE_ERROR"
    MODEL_ERROR = "MODEL_ERROR"


# ============================================================================
# Helper Functions
# ============================================================================

def create_success_response(
    message_id: str,
    reply: str,
    intent: str,
    conversation_id: str,
    wallet_balance: float,
    components: Optional[MessageComponents] = None,
    message_type: MessageType = MessageType.TEXT,
    metadata: Optional[MessageMetadata] = None,
    notice: Optional[str] = None,
    original_message: Optional[str] = None,
    enriched_message: Optional[str] = None,
) -> SendMessageResponse:
    """Helper function to create a successful response"""
    return SendMessageResponse(
        success=True,
        data=MessageData(
            messageId=message_id,
            reply=reply,
            intent=intent,
            originalMessage=original_message,
            enrichedMessage=enriched_message,
            conversationId=conversation_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            messageType=message_type,
            components=components,
            walletBalance=wallet_balance,
            notice=notice,
        ),
        metadata=metadata
    )


def create_error_response(
    error_code: str,
    error_message: str,
    details: Optional[Dict[str, Any]] = None,
    wallet_balance: Optional[float] = None,
    components: Optional[MessageComponents] = None
) -> SendMessageResponse:
    """Helper function to create an error response"""
    return SendMessageResponse(
        success=False,
        error=ErrorDetail(
            code=error_code,
            message=error_message,
            details=details,
            walletBalance=wallet_balance,
            components=components
        )
    )

