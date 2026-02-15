# cURL Examples for Frontend Team

**Base URL:** `http://localhost:8502` (Development)  
**Production URL:** Update with your production domain

---

## How User Queries Flow to AI

### Request Flow:
1. **Frontend** → Sends POST request with user message to backend API
2. **Backend API** (`/api/chat/message`) → Receives request and extracts:
   - User message
   - Conversation context (userId, conversationId, etc.)
   - Chat history (optional)
3. **Knowledge Base Retrieval** → Backend queries AWS Bedrock Knowledge Base with user's query to retrieve relevant documents
4. **LLM Processing** → Backend sends to AWS Bedrock (Mistral model):
   - User's query
   - Retrieved knowledge base context
   - Chat history (for conversation continuity)
   - System prompt (defines AI behavior)
5. **Response Generation** → LLM generates response using:
   - Knowledge base context (primary source of truth)
   - Conversation history
   - System instructions
6. **Backend Processing** → Extracts intent, agent suggestions, wallet balance
7. **Frontend** ← Receives structured response with AI reply and UI components

### Key Technologies:
- **LLM Model:** AWS Bedrock Mistral Large (`mistral.mistral-large-2402-v1:0`)
- **Knowledge Base:** AWS Bedrock Knowledge Bases (RAG - Retrieval Augmented Generation)
- **Framework:** FastAPI (Python)

---

## Quick Reference: Complete Request Structure

### Complete cURL Example with All Fields:

```bash
curl -X POST http://localhost:8502/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What AI agents are available?",
    "conversationId": "conv_123456",
    "messageType": "text",
    "context": {
      "userId": "user_123",
      "username": "John Doe",
      "wallet_balance": 1500.0,
      "marketplaces_registered": ["Amazon", "Flipkart", "Walmart"],
      "loginLocation": "India",
      "previousIntent": "agent_suggestion",
      "clientInfo": {
        "device": "desktop",
        "appVersion": "1.0.0",
        "timezone": "Asia/Kolkata",
        "platform": "web",
        "userAgent": "Mozilla/5.0...",
        "country": "IN"
      },
      "metadata": {}
    },
    "language": "English"
  }'
```

### Key Context Fields:

- **`wallet_balance`** (float, optional): Current wallet balance - used for agent cost calculations and currency conversion
- **`marketplaces_registered`** (array, optional): List of user's registered marketplaces - e.g., `["Amazon", "Flipkart", "Walmart"]`
- **`loginLocation`** (string, optional): User's location - `"India"` → INR (₹), `"US"` or `"Other"` → USD ($)
- **`username`** (string, optional): User's display name - used for personalized responses
- **`previousIntent`** (string, optional): Previous detected intent for conversation continuity

---

## Endpoint 1: Optimized Chat Endpoint (Recommended)

### Endpoint: `POST /api/chat/message`

This is the **recommended endpoint** with structured responses, error handling, and rich UI components.

### Complete Example (All Fields Including Wallet Balance & Marketplaces):

```bash
curl -X POST http://localhost:8502/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What AI agents are available?",
    "conversationId": "conv_123456",
    "messageType": "text",
    "context": {
      "userId": "user_123",
      "username": "John Doe",
      "wallet_balance": 1500.0,
      "marketplaces_registered": ["Amazon", "Flipkart", "Walmart"],
      "loginLocation": "India",
      "clientInfo": {
        "device": "desktop",
        "appVersion": "1.0.0",
        "timezone": "Asia/Kolkata",
        "platform": "web",
        "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "country": "IN"
      }
    },
    "language": "English"
  }'
```

### Basic Example (Minimal Required Fields):

```bash
curl -X POST http://localhost:8502/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What AI agents are available?",
    "conversationId": "conv_123456",
    "messageType": "text",
    "context": {
      "userId": "user_123",
      "clientInfo": {
        "device": "desktop",
        "appVersion": "1.0.0",
        "timezone": "Asia/Kolkata",
        "platform": "web"
      }
    },
    "language": "English"
  }'
```

### Example with Wallet Balance Only:

```bash
curl -X POST http://localhost:8502/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "How do I create better product listings?",
    "conversationId": "conv_abc123",
    "context": {
      "userId": "user_456",
      "wallet_balance": 2500.0,
      "clientInfo": {
        "device": "mobile",
        "appVersion": "1.0.0",
        "timezone": "UTC",
        "platform": "ios"
      }
    }
  }'
```

### Example with Registered Marketplaces Only:

```bash
curl -X POST http://localhost:8502/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me analytics for my marketplaces",
    "conversationId": "conv_abc123",
    "context": {
      "userId": "user_456",
      "marketplaces_registered": ["Amazon", "eBay", "Shopify"],
      "clientInfo": {
        "device": "desktop",
        "appVersion": "1.0.0",
        "timezone": "America/New_York",
        "platform": "web",
        "country": "US"
      }
    }
  }'
```

### Example with All Context Fields (Complete):

```bash
curl -X POST http://localhost:8502/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Tell me more about that agent",
    "conversationId": "conv_123456",
    "messageType": "text",
    "context": {
      "userId": "user_123",
      "username": "Jane Smith",
      "wallet_balance": 3200.5,
      "marketplaces_registered": ["Amazon", "Flipkart", "Walmart", "eBay"],
      "loginLocation": "India",
      "previousIntent": "agent_suggestion",
      "clientInfo": {
        "device": "desktop",
        "appVersion": "1.0.0",
        "timezone": "Asia/Kolkata",
        "platform": "web",
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "country": "IN"
      },
      "metadata": {
        "sessionId": "session_abc123",
        "referrer": "dashboard"
      }
    },
    "language": "English"
  }'
```

### Example for US User (USD Currency):

```bash
curl -X POST http://localhost:8502/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What agents can help with my Amazon listings?",
    "conversationId": "conv_789",
    "context": {
      "userId": "user_us_001",
      "username": "Mike Johnson",
      "wallet_balance": 500.0,
      "marketplaces_registered": ["Amazon", "Walmart"],
      "loginLocation": "US",
      "clientInfo": {
        "device": "desktop",
        "appVersion": "1.0.0",
        "timezone": "America/New_York",
        "platform": "web",
        "country": "US"
      }
    },
    "language": "English"
  }'
```

### Success Response Example (With Wallet Balance & Marketplaces):

```json
{
  "success": true,
  "data": {
    "messageId": "msg_abc123def456",
    "reply": "Here are the available AI agents:\n\n- **Smart Listing Agent** - Creates optimized product listings\n- **Text Grading Agent** - Improves product descriptions\n...",
    "intent": "product_detail",
    "conversationId": "conv_123456",
    "timestamp": "2025-12-30T12:00:00.000Z",
    "messageType": "text",
    "walletBalance": 1500.0,
    "components": {
      "agentCard": {
        "agentId": "smart-listing",
        "name": "Smart Listing Agent",
        "icon": "📝",
        "cost": 50.0,
        "currency": "INR",
        "currencySymbol": "₹",
        "walletAfter": 1450.0,
        "features": ["Multi-marketplace", "SEO optimized", "Keyword research"],
        "action": "launch_agent",
        "marketplace": ["Amazon", "Flipkart", "Walmart"],
        "description": "Creates optimized product listings for your registered marketplaces"
      },
      "suggestedAgents": [
        {
          "agentId": "text-grading",
          "name": "Text Grading Agent",
          "icon": "✍️",
          "cost": 30.0,
          "currency": "INR",
          "currencySymbol": "₹",
          "walletAfter": 1470.0,
          "features": ["Grammar check", "SEO optimization"],
          "action": "launch_agent",
          "marketplace": ["Amazon", "Flipkart"]
        }
      ],
      "quickActions": [
        {
          "label": "View Pricing",
          "actionType": "url",
          "url": "/pricing",
          "icon": "💰"
        }
      ]
    }
  },
  "metadata": {
    "modelVersion": "mistral.mistral-large-2402-v1:0",
    "latencyMs": 1250.5,
    "requestId": "req_xyz789",
    "inputTokens": 450,
    "outputTokens": 320,
    "tokensUsed": 770
  }
}
```

### Error Response Example (Insufficient Balance):

```json
{
  "success": false,
  "error": {
    "code": "INSUFFICIENT_BALANCE",
    "message": "Insufficient balance John Doe. You need ₹50.00 to use this agent.",
    "details": {
      "required": 50,
      "current": 25,
      "shortfall": 25
    },
    "walletBalance": 25.0,
    "components": {
      "quickActions": [
        {
          "label": "Click here to Top-up",
          "actionType": "url",
          "url": "https://mysellercentral.com/ai-agents/",
          "icon": "💳"
        }
      ]
    }
  }
}
```

### Error Response Example (US User - USD Currency):

```json
{
  "success": false,
  "error": {
    "code": "INSUFFICIENT_BALANCE",
    "message": "Insufficient balance Mike. You need $5.00 to use this agent.",
    "details": {
      "required": 5.0,
      "current": 2.5,
      "shortfall": 2.5
    },
    "walletBalance": 2.5,
    "components": {
      "quickActions": [
        {
          "label": "Click here to Top-up",
          "actionType": "url",
          "url": "https://mysellercentral.com/ai-agents/",
          "icon": "💳"
        }
      ]
    }
  }
}
```

---

## Endpoint 2: Legacy Chat Endpoint (Backward Compatibility)

### Endpoint: `POST /api/chat`

Simpler endpoint for basic chat functionality. Use this if you don't need structured components.

### cURL Example:

```bash
curl -X POST http://localhost:8502/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are your pricing plans?",
    "language": "English",
    "chat_history": [
      {
        "role": "user",
        "content": "Hello"
      },
      {
        "role": "assistant",
        "content": "Hi! How can I help you with MySellerCentral?"
      }
    ]
  }'
```

### Minimal Example:

```bash
curl -X POST http://localhost:8502/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "How do I optimize my Amazon listings?"
  }'
```

### Success Response:

```json
{
  "response": "To optimize your Amazon listings, you can use our **Smart Listing Agent** which:\n\n- Analyzes top-performing listings\n- Generates SEO-optimized titles and descriptions\n- Suggests keywords based on competitor analysis\n\nWould you like to try it?",
  "status": "success"
}
```

---

## Health Check Endpoint

### Endpoint: `GET /health`

```bash
curl http://localhost:8502/health
```

**Response:**
```json
{
  "status": "healthy"
}
```

---

## Root Endpoint (API Info)

### Endpoint: `GET /`

```bash
curl http://localhost:8502/
```

**Response:**
```json
{
  "status": "ok",
  "message": "MySellerCentral Chatbot API is running",
  "version": "2.0.0",
  "endpoints": {
    "sendMessage": "/api/chat/message",
    "openConversation": "/api/chat/conversation/{conversation_id}",
    "getConversationMessages": "/api/chat/conversation/{conversation_id}/messages",
    "getUserConversations": "/api/user/{user_id}/conversations",
    "legacyChat": "/api/chat",
    "health": "/health"
  }
}
```

---

## Open Conversation Endpoint

### Endpoint: `GET /api/chat/conversation/{conversation_id}`

Opens a conversation by conversationId. Designed for when a user clicks on a conversation from the sidebar to view its history. Works independently of user_id - only requires conversation_id.

### cURL Example:

```bash
curl -X GET "http://localhost:8502/api/chat/conversation/conv_123456789" \
  -H "Content-Type: application/json"
```

### With Pretty Print (using jq):

```bash
curl -X GET "http://localhost:8502/api/chat/conversation/conv_123456789" \
  -H "Content-Type: application/json" | jq '.'
```

### Success Response:

```json
{
  "success": true,
  "data": {
    "conversation": {
      "conversationId": "conv_123456789",
      "userId": "user_123",
      "status": "active",
      "title": "Product Inquiry",
      "createdAt": "2024-01-15T10:30:00",
      "updatedAt": "2024-01-15T11:45:00",
      "lastMessageAt": "2024-01-15T11:45:00",
      "stats": {
        "messageCount": 10,
        "totalTokens": 5000
      },
      "clientInfo": {
        "device": "desktop",
        "appVersion": "1.0.0",
        "timezone": "Asia/Kolkata",
        "platform": "web"
      }
    },
    "messages": [
      {
        "messageId": "msg_001",
        "role": "user",
        "content": "What AI agents are available?",
        "timestamp": "2024-01-15T10:30:00"
      },
      {
        "messageId": "msg_002",
        "role": "assistant",
        "content": "We have several AI agents available...",
        "timestamp": "2024-01-15T10:30:15"
      }
    ],
    "messageCount": 10
  },
  "requestId": "req_abc123"
}
```

### Error Responses:

**404 - Conversation Not Found:**
```json
{
  "detail": "Conversation not found: conv_123456789"
}
```

**503 - Service Unavailable:**
```json
{
  "detail": "Conversation storage service not available"
}
```

---

## Request Field Details

### SendMessageRequest (Optimized Endpoint)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | ✅ Yes | User's message/query |
| `conversationId` | string | ✅ Yes | Unique conversation identifier (use `"new"` or `""` for new conversations) |
| `messageType` | enum | No | `"text"`, `"voice"`, or `"image"` (default: `"text"`) |
| `context` | object | ✅ Yes | Request context |
| `context.userId` | string | ✅ Yes | Unique user identifier |
| `context.username` | string | No | User's display name (used for personalization in responses) |
| `context.wallet_balance` | float | No | User's current wallet balance (used for agent cost calculations and currency conversion) |
| `context.marketplaces_registered` | array | No | List of marketplaces user is registered on (e.g., `["Amazon", "Flipkart", "Walmart"]`) |
| `context.loginLocation` | string | No | User's login location (e.g., `"India"`, `"US"`, `"Other"`). Used to determine currency (INR for India, USD for others) |
| `context.previousIntent` | string | No | Previous detected intent |
| `context.clientInfo` | object | ✅ Yes | Client device information |
| `context.clientInfo.device` | string | ✅ Yes | `"mobile"`, `"desktop"`, or `"tablet"` |
| `context.clientInfo.appVersion` | string | ✅ Yes | Application version |
| `context.clientInfo.timezone` | string | ✅ Yes | User timezone (e.g., `"Asia/Kolkata"`, `"America/New_York"`) |
| `context.clientInfo.platform` | string | No | `"ios"`, `"android"`, or `"web"` |
| `context.clientInfo.userAgent` | string | No | User agent string |
| `context.clientInfo.country` | string | No | User country code (e.g., `"IN"`, `"US"`). If not provided, will be derived from timezone |
| `context.metadata` | object | No | Additional metadata (key-value pairs) |
| `language` | string | No | Response language (default: `"English"`) |

### ChatRequest (Legacy Endpoint)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | ✅ Yes | User's message/query |
| `language` | string | No | Response language (default: `"English"`) |
| `chat_history` | array | No | Previous conversation messages |

---

## Supported Languages

- `English` (default)
- `Spanish`
- `Hindi`
- `French`
- `German`

---

## Error Handling

### Common Error Codes:

- `INSUFFICIENT_BALANCE` - User doesn't have enough tokens for agent
- `AGENT_UNAVAILABLE` - Requested agent is not available
- `INVALID_CONVERSATION` - Conversation ID is invalid
- `RATE_LIMIT_EXCEEDED` - Too many requests
- `INTERNAL_ERROR` - Server error
- `VALIDATION_ERROR` - Invalid request format
- `MODEL_ERROR` - AI model error

### HTTP Status Codes:

- `200` - Success
- `422` - Validation error (missing/invalid fields)
- `500` - Server error

---

## JavaScript/Fetch Examples

### Using Optimized Endpoint (Complete Example):

```javascript
const response = await fetch('http://localhost:8502/api/chat/message', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    message: 'What AI agents are available?',
    conversationId: 'conv_123456',
    messageType: 'text',
    context: {
      userId: 'user_123',
      username: 'John Doe',
      wallet_balance: 1500.0,
      marketplaces_registered: ['Amazon', 'Flipkart', 'Walmart'],
      loginLocation: 'India',
      clientInfo: {
        device: 'desktop',
        appVersion: '1.0.0',
        timezone: 'Asia/Kolkata',
        platform: 'web',
        userAgent: navigator.userAgent,
        country: 'IN'
      }
    },
    language: 'English'
  })
});

const data = await response.json();

if (data.success) {
  console.log('AI Reply:', data.data.reply);
  console.log('Wallet Balance:', data.data.walletBalance);
  console.log('Intent:', data.data.intent);
  
  if (data.data.components?.agentCard) {
    const agent = data.data.components.agentCard;
    console.log('Suggested Agent:', agent.name);
    console.log('Cost:', `${agent.currencySymbol}${agent.cost}`);
    console.log('Wallet After:', `${agent.currencySymbol}${agent.walletAfter}`);
    console.log('Supported Marketplaces:', agent.marketplace);
  }
  
  if (data.metadata) {
    console.log('Tokens Used:', data.metadata.tokensUsed);
    console.log('Latency:', data.metadata.latencyMs, 'ms');
  }
} else {
  console.error('Error:', data.error.message);
  console.error('Wallet Balance:', data.error.walletBalance);
  
  if (data.error.components?.quickActions) {
    console.log('Quick Actions:', data.error.components.quickActions);
  }
}
```

### Using Legacy Endpoint:

```javascript
const response = await fetch('http://localhost:8502/api/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    message: 'What are your pricing plans?',
    language: 'English',
    chat_history: []
  })
});

const data = await response.json();
console.log('AI Reply:', data.response);
```

---

## Notes for Frontend Team

1. **Always use the optimized endpoint** (`/api/chat/message`) for new implementations
2. **Response contains Markdown** - Use a Markdown renderer (e.g., `react-markdown`, `marked`)
3. **Include `conversationId`** - Use the same ID for all messages in a conversation. Use `"new"` or `""` for new conversations
4. **Wallet Balance** - Always send `wallet_balance` in the request context. The backend uses it for:
   - Currency conversion (INR for India, USD for US/Other)
   - Agent cost calculations
   - Wallet balance validation
5. **Registered Marketplaces** - Send `marketplaces_registered` array in context. This helps the AI:
   - Provide marketplace-specific recommendations
   - Filter agents by supported marketplaces
   - Personalize responses based on user's marketplaces
6. **Login Location** - Send `loginLocation` to determine currency:
   - `"India"` → INR (₹)
   - `"US"` or `"Other"` → USD ($)
7. **Username** - Send `username` for personalized responses (e.g., "Insufficient balance John Doe...")
8. **Components** - Use `data.components` for rich UI (agent cards, quick actions)
9. **Error Handling** - Always check `success` field before accessing `data`
10. **Chat History** - Backend automatically retrieves chat history from database. No need to send it in the request
11. **CORS** - Backend allows all origins in development. Update for production.
12. **Currency Display** - Agent costs are automatically converted based on `loginLocation`. Check `currency` and `currencySymbol` in agent cards

---

## Testing Checklist

- [ ] Health check endpoint works
- [ ] Optimized endpoint accepts valid request
- [ ] Legacy endpoint accepts valid request
- [ ] Error responses are properly formatted
- [ ] Markdown in responses renders correctly
- [ ] Agent cards display when suggested
- [ ] Wallet balance is shown correctly
- [ ] Different languages work
- [ ] Invalid requests return 422 errors

