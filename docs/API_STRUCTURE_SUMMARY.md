# API Structure Summary - User Request & AI Response

## Overview
The API uses a standardized request/response structure with consistent error handling and rich UI components.

---

## 1. USER REQUEST STRUCTURE

### Endpoint: `POST /api/chat/message`

### Request Body Schema

```json
{
  "message": "string (required, min_length=1)",
  "conversationId": "string (required)",
  "messageType": "text | voice | image (default: text)",
  "context": {
    "userId": "string (required)",
    "previousIntent": "string (optional)",
    "clientInfo": {
      "device": "string (required) - mobile | desktop | tablet",
      "appVersion": "string (required)",
      "timezone": "string (required) - e.g., Asia/Kolkata",
      "platform": "string (optional) - ios | android | web",
      "userAgent": "string (optional)"
    },
    "metadata": {
      "key": "value (optional, any additional metadata)"
    }
  },
  "language": "string (optional, default: English)"
}
```

### Request Fields Breakdown

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | ✅ Yes | User's message text (minimum 1 character) |
| `conversationId` | string | ✅ Yes | Unique conversation identifier for tracking context |
| `messageType` | enum | No | Type of message: `text`, `voice`, or `image` (default: `text`) |
| `context` | object | ✅ Yes | Request context information |
| `context.userId` | string | ✅ Yes | Unique user identifier |
| `context.previousIntent` | string | No | Previously detected intent (for context) |
| `context.clientInfo` | object | ✅ Yes | Client device and app information |
| `context.clientInfo.device` | string | ✅ Yes | Device type: `mobile`, `desktop`, or `tablet` |
| `context.clientInfo.appVersion` | string | ✅ Yes | Application version number |
| `context.clientInfo.timezone` | string | ✅ Yes | User's timezone (e.g., `Asia/Kolkata`) |
| `context.clientInfo.platform` | string | No | Platform: `ios`, `android`, or `web` |
| `context.clientInfo.userAgent` | string | No | User agent string |
| `context.metadata` | object | No | Additional metadata (key-value pairs) |
| `language` | string | No | Response language (default: `English`) |

### Example Request

```json
{
  "message": "I want to improve my product images",
  "conversationId": "conv_123456",
  "messageType": "text",
  "context": {
    "userId": "user_789",
    "previousIntent": "general_query",
    "clientInfo": {
      "device": "mobile",
      "appVersion": "1.2.3",
      "timezone": "Asia/Kolkata",
      "platform": "ios",
      "userAgent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)"
    },
    "metadata": {
      "sessionId": "sess_abc123"
    }
  },
  "language": "English"
}
```

---

## 2. AI RESPONSE STRUCTURE

### Success Response (200 OK)

```json
{
  "success": true,
  "data": {
    "messageId": "string",
    "reply": "string (AI's response text, may contain Markdown)",
    "intent": "string (detected intent type)",
    "conversationId": "string",
    "timestamp": "string (ISO 8601 format)",
    "messageType": "text | voice | image",
    "components": {
      "agentCard": {
        "agentId": "string",
        "name": "string",
        "icon": "string (emoji)",
        "cost": "number (tokens/currency)",
        "walletAfter": "number (projected balance after using agent)",
        "features": ["string"],
        "action": "string (default: launch_agent)",
        "marketplace": ["string"],
        "description": "string (optional)",
        "quickActions": [
          {
            "label": "string",
            "message": "string (optional)",
            "url": "string (optional)",
            "actionType": "message | url | deep_link | launch_agent",
            "icon": "string (optional, emoji)"
          }
        ]
      },
      "suggestedAgents": [
        {
          "agentId": "string",
          "name": "string",
          "icon": "string",
          "cost": "number",
          "walletAfter": "number",
          "features": ["string"],
          "action": "string",
          "marketplace": ["string"],
          "quickActions": []
        }
      ],
      "quickActions": [
        {
          "label": "string",
          "message": "string (optional)",
          "url": "string (optional)",
          "actionType": "message | url | deep_link | launch_agent",
          "icon": "string (optional)"
        }
      ],
      "pricingInfo": "object | null",
      "marketplaceInfo": "object | null"
    },
    "walletBalance": "number (current wallet balance, server-validated)"
  },
  "metadata": {
    "modelVersion": "string",
    "tokensUsed": "number (optional)",
    "latencyMs": "number (optional, milliseconds)",
    "knowledgeBaseHits": "number (optional)",
    "requestId": "string (optional, for tracing)"
  }
}
```

### Error Response (200 OK with success: false)

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "string (error code)",
    "message": "string (human-readable error message)",
    "details": {
      "key": "value (optional, additional error details)"
    },
    "walletBalance": "number (optional, current wallet balance if relevant)"
  },
  "metadata": null
}
```

### Response Fields Breakdown

#### Success Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Always `true` for successful responses |
| `data` | object | Response data (present when `success=true`) |
| `data.messageId` | string | Unique message identifier (format: `msg_<hex>`) |
| `data.reply` | string | AI assistant's reply text (may contain Markdown) |
| `data.intent` | string | Detected intent type (see Intent Types below) |
| `data.conversationId` | string | Conversation identifier (echoed from request) |
| `data.timestamp` | string | ISO 8601 timestamp (UTC) |
| `data.messageType` | string | Message type: `text`, `voice`, or `image` |
| `data.components` | object\|null | Structured UI components (null if not applicable) |
| `data.components.agentCard` | object\|null | Primary agent suggestion card |
| `data.components.suggestedAgents` | array | Alternative agent suggestions |
| `data.components.quickActions` | array | Quick action buttons |
| `data.components.pricingInfo` | object\|null | Pricing information (if pricing query) |
| `data.components.marketplaceInfo` | object\|null | Marketplace information (if marketplace query) |
| `data.walletBalance` | number | Current wallet balance (server-validated) |
| `metadata` | object\|null | Response metadata |
| `metadata.modelVersion` | string | AI model version used |
| `metadata.tokensUsed` | number | Tokens consumed (optional) |
| `metadata.latencyMs` | number | Response latency in milliseconds |
| `metadata.knowledgeBaseHits` | number | Number of knowledge base documents retrieved |
| `metadata.requestId` | string | Request ID for tracing |

#### Error Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Always `false` for error responses |
| `data` | null | Always `null` for error responses |
| `error` | object | Error details (present when `success=false`) |
| `error.code` | string | Error code (see Error Codes below) |
| `error.message` | string | Human-readable error message |
| `error.details` | object | Additional error details (optional) |
| `error.walletBalance` | number | Current wallet balance (if relevant) |
| `metadata` | null | Always `null` for error responses |

---

## 3. INTENT TYPES

The API detects and returns one of the following intent types:

| Intent Type | Description |
|-------------|-------------|
| `agent_suggestion` | User wants to use/do something that matches a specific AI agent |
| `pricing_query` | User is asking about pricing information |
| `feature_query` | User wants to know about features/capabilities |
| `marketplace_query` | User is asking about marketplace integrations |
| `general_query` | General question (default) |
| `onboarding` | Onboarding flow |
| `support` | Support request |

---

## 4. ERROR CODES

| Error Code | Description |
|------------|-------------|
| `INSUFFICIENT_BALANCE` | User doesn't have enough tokens/wallet balance |
| `AGENT_UNAVAILABLE` | Requested agent is currently unavailable |
| `INVALID_CONVERSATION` | Conversation ID is invalid or doesn't belong to user |
| `RATE_LIMIT_EXCEEDED` | User has exceeded rate limit |
| `INTERNAL_ERROR` | Unexpected server error |
| `VALIDATION_ERROR` | Request validation failed |
| `KNOWLEDGE_BASE_ERROR` | Error accessing knowledge base |
| `MODEL_ERROR` | Error with AI model service |

---

## 5. COMPONENT STRUCTURES

### AgentCard Component

Displays agent information with cost and features.

```json
{
  "agentId": "string (e.g., 'image-grading-enhancement')",
  "name": "string (e.g., 'Image Grading & Enhancement')",
  "icon": "string (emoji, e.g., '🖼️')",
  "cost": "number (tokens required, e.g., 18)",
  "walletAfter": "number (projected balance after using agent)",
  "features": ["string (e.g., 'Quality scoring', 'Resolution analysis')"],
  "action": "string (default: 'launch_agent')",
  "marketplace": ["string (e.g., 'Amazon', 'Walmart')"],
  "description": "string (optional)",
  "quickActions": [
    {
      "label": "string",
      "message": "string (optional, message to send when clicked)",
      "url": "string (optional, URL to navigate to)",
      "actionType": "message | url | deep_link | launch_agent",
      "icon": "string (optional, emoji)"
    }
  ]
}
```

### QuickAction Component

Action buttons for quick user interactions.

```json
{
  "label": "string (button label)",
  "message": "string (optional, message to send when clicked)",
  "url": "string (optional, URL to navigate to)",
  "actionType": "message | url | deep_link | launch_agent",
  "icon": "string (optional, emoji)"
}
```

---

## 6. EXAMPLE RESPONSES

### Success Response Example

```json
{
  "success": true,
  "data": {
    "messageId": "msg_abc123def456",
    "reply": "I can help you improve your product images! The **Image Grading & Enhancement** agent is perfect for this. It analyzes image quality, checks compliance, and provides enhancement suggestions.\n\n**Key Features:**\n- Quality scoring\n- Resolution analysis\n- Compliance check\n\n**Cost:** 18 tokens\n**Marketplace:** Amazon, Walmart\n\nWould you like to launch this agent?",
    "intent": "agent_suggestion",
    "conversationId": "conv_123456",
    "timestamp": "2024-12-29T14:30:00.000Z",
    "messageType": "text",
    "components": {
      "agentCard": {
        "agentId": "image-grading-enhancement",
        "name": "Image Grading & Enhancement",
        "icon": "🖼️",
        "cost": 18,
        "walletAfter": 227,
        "features": [
          "Quality scoring",
          "Resolution analysis",
          "Compliance check"
        ],
        "action": "launch_agent",
        "marketplace": ["Amazon", "Walmart"],
        "description": null,
        "quickActions": [
          {
            "label": "Image Tips",
            "message": "What image standards does Image Grading & Enhancement check?",
            "actionType": "message",
            "icon": "📸"
          },
          {
            "label": "Use Now",
            "message": null,
            "actionType": "launch_agent",
            "icon": "✨"
          }
        ]
      },
      "suggestedAgents": [],
      "quickActions": [],
      "pricingInfo": null,
      "marketplaceInfo": null
    },
    "walletBalance": 245
  },
  "metadata": {
    "modelVersion": "mistral.mistral-large-2402-v1:0",
    "tokensUsed": null,
    "latencyMs": 234.5,
    "knowledgeBaseHits": null,
    "requestId": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

### Error Response Example (Insufficient Balance)

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "INSUFFICIENT_BALANCE",
    "message": "Insufficient balance. You need 18 tokens to use this agent.",
    "details": {
      "required": 18,
      "current": 10,
      "shortfall": 8
    },
    "walletBalance": 10
  },
  "metadata": null
}
```

### Error Response Example (Model Error)

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "MODEL_ERROR",
    "message": "Failed to generate response from AI model",
    "details": {
      "error": "Connection timeout to Bedrock service"
    },
    "walletBalance": 245
  },
  "metadata": null
}
```

---

## 7. IMPLEMENTATION NOTES

### Key Points

1. **Wallet Balance**: Always fetched server-side from microservice (not from client)
2. **Error Handling**: Always check `success` field first before accessing `data` or `error`
3. **Components**: May be `null` if no structured components are needed
4. **Metadata**: Optional but recommended for monitoring and debugging
5. **Message ID**: Generated server-side with format `msg_<12-char-hex>`
6. **Timestamp**: Always in ISO 8601 format with UTC timezone (ends with 'Z')
7. **Reply Text**: May contain Markdown formatting - render with a Markdown library
8. **Multiple Agents**: When multiple agents are detected, first goes to `agentCard`, others to `suggestedAgents`
9. **Intent Detection**: Uses LLM structured output + keyword fallback for reliability

### Response Processing Flow

1. **Request Validation**: Validate request structure and required fields
2. **Wallet Balance Fetch**: Fetch current wallet balance from microservice
3. **LLM Processing**: Process message with AI model (with knowledge base retrieval)
4. **Intent Extraction**: Extract intent and agent IDs from LLM response
5. **Component Generation**: Generate UI components based on intent
6. **Balance Check**: Verify sufficient balance for agent suggestions
7. **Response Assembly**: Assemble standardized response with metadata

### Legacy Endpoint

The API also supports a legacy endpoint `POST /api/chat` for backward compatibility:

**Request:**
```json
{
  "message": "string",
  "language": "string (optional)",
  "chat_history": [
    {
      "role": "user | assistant",
      "content": "string"
    }
  ]
}
```

**Response:**
```json
{
  "response": "string",
  "status": "success"
}
```

---

## 8. FILES REFERENCE

- **`src/core/models.py`** - Pydantic models for request/response validation
- **`src/api/routes.py`** - FastAPI endpoints and request handling
- **`src/core/backend.py`** - LLM integration with async support
- **`src/services/intent_extractor.py`** - Intent detection and component generation
- **`src/services/agent_service.py`** - Agent database and information
- **`src/services/wallet_service.py`** - Wallet microservice client
- **`docs/API_RESPONSE_EXAMPLES.json`** - Complete response examples

---

## 9. USAGE EXAMPLE

```javascript
// Send message request
const requestBody = {
  message: "I want to improve my product images",
  conversationId: "conv_123456",
  messageType: "text",
  context: {
    userId: "user_789",
    previousIntent: "general_query",
    clientInfo: {
      device: "mobile",
      appVersion: "1.2.3",
      timezone: "Asia/Kolkata",
      platform: "ios",
      userAgent: navigator.userAgent
    },
    metadata: {}
  },
  language: "English"
};

const response = await fetch('http://localhost:8502/api/chat/message', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(requestBody)
});

const result = await response.json();

// Check success
if (result.success) {
  // Access response data
  const reply = result.data.reply;
  const intent = result.data.intent;
  const walletBalance = result.data.walletBalance;
  const agentCard = result.data.components?.agentCard;
  const suggestedAgents = result.data.components?.suggestedAgents;
  
  // Render reply (may contain Markdown)
  renderMarkdown(reply);
  
  // Render agent card if available
  if (agentCard) {
    renderAgentCard(agentCard);
  }
  
  // Render suggested agents
  if (suggestedAgents && suggestedAgents.length > 0) {
    renderSuggestedAgents(suggestedAgents);
  }
} else {
  // Handle error
  const errorCode = result.error.code;
  const errorMessage = result.error.message;
  const errorDetails = result.error.details;
  
  showError(errorMessage);
  
  // Handle specific error codes
  if (errorCode === 'INSUFFICIENT_BALANCE') {
    showWalletTopUpPrompt(result.error.walletBalance);
  }
}
```

---

## Summary

- **User Request**: Structured with message, conversationId, context (userId, clientInfo), and optional metadata
- **AI Response**: Standardized with `success` flag, `data` (for success) or `error` (for failure), and optional `metadata`
- **Components**: Rich UI components (AgentCard, QuickActions) generated based on detected intent
- **Error Handling**: Consistent error structure with codes, messages, and details
- **Wallet Integration**: Server-side wallet balance validation and projection


