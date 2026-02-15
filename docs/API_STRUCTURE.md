# Optimized API Structure Documentation

## Overview

The API now uses a consistent, optimized structure with standardized error handling and rich response components.

## Endpoint

### POST `/api/chat/message`

Send a chat message and receive a structured response with components.

#### Request Body

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
      "userAgent": "Mozilla/5.0..."
    },
    "metadata": {}
  },
  "language": "English"
}
```

#### Success Response (200)

```json
{
  "success": true,
  "data": {
    "messageId": "msg_abc123",
    "reply": "I can help with Image Grading & Enhancement!",
    "intent": "agent_suggestion",
    "conversationId": "conv_123456",
    "timestamp": "2024-12-29T14:30:00.000Z",
    "messageType": "text",
    "components": {
      "agentCard": {
        "agentId": "image-grading",
        "name": "Image Grading & Enhancement",
        "icon": "🖼️",
        "cost": 18,
        "walletAfter": 227,
        "features": ["Quality scoring", "Resolution analysis", "Compliance check"],
        "action": "launch_agent",
        "marketplace": ["Amazon", "Walmart"]
      },
      "quickActions": [
        {"label": "View All Features", "message": "Show me all features", "actionType": "message"},
        {"label": "Check Pricing", "message": "What's your pricing?", "actionType": "message"}
      ]
    },
    "walletBalance": 245
  },
  "metadata": {
    "modelVersion": "claude-3-haiku-20240307",
    "latencyMs": 234.5,
    "requestId": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

#### Error Response (200 with success: false)

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

## Error Codes

- `INSUFFICIENT_BALANCE` - User doesn't have enough tokens
- `AGENT_UNAVAILABLE` - Requested agent is unavailable
- `INVALID_CONVERSATION` - Invalid conversation ID
- `RATE_LIMIT_EXCEEDED` - Rate limit exceeded
- `INTERNAL_ERROR` - Unexpected server error
- `VALIDATION_ERROR` - Request validation failed
- `KNOWLEDGE_BASE_ERROR` - Knowledge base access error
- `MODEL_ERROR` - AI model service error

## Intent Types

- `agent_suggestion` - AI agent recommendation
- `pricing_query` - Pricing information request
- `feature_query` - Feature information request
- `marketplace_query` - Marketplace-related query
- `general_query` - General question
- `onboarding` - Onboarding flow
- `support` - Support request

## Message Types

- `text` - Text message (default)
- `voice` - Voice message
- `image` - Image message

## Components

### AgentCard
Displays agent information with cost and features.

### QuickActions
Action buttons for quick user interactions.

## Legacy Endpoint

### POST `/api/chat`

Still available for backward compatibility. Returns simple response format.

## Files Structure

- `models.py` - Pydantic models for request/response
- `wallet_service.py` - Wallet microservice client
- `intent_extractor.py` - Intent detection and component generation
- `api.py` - FastAPI endpoints
- `backend.py` - LLM integration with async support
- `API_RESPONSE_EXAMPLES.json` - Complete response examples

## Integration Notes

1. **Wallet Balance**: Fetched server-side from microservice (not from client)
2. **Error Handling**: Always check `success` field first
3. **Components**: May be `null` if no structured components are needed
4. **Metadata**: Optional but recommended for monitoring

