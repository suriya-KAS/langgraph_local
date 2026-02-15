# MySellerCentral Chatbot - Comprehensive Documentation

## Executive Summary

### What is This System?

The MySellerCentral Chatbot is an intelligent, AI-powered conversational assistant designed to help e-commerce sellers navigate and utilize the MySellerCentral platform. It provides:

- **24/7 Support**: Instant answers about platform features, pricing, AI agents, and marketplace integrations
- **Multi-language Support**: Responds in English, Spanish, Hindi, French, and German
- **Context-Aware Conversations**: Maintains conversation history with intelligent summarization
- **Analytics Integration**: Connects to external analytics APIs for user data queries

### Key Technologies

- **Backend Framework**: FastAPI (Python)
- **AI/LLM**: AWS Bedrock (Mistral Large 2402)
- **Knowledge Base**: Amazon Bedrock Knowledge Bases (vector search)
- **Database**: MongoDB (conversation storage)
- **Frontend**: Streamlit (web interface)
- **AI Framework**: LangChain

### System Scale

- **Supported Languages**: English (as of now)
- **AI Agents**: 10+ specialized agents
- **Marketplaces**: Amazon, Walmart, Shopify, ONDC
- **API Endpoints**: 4 main endpoints + health checks
- **Database Collections**: 2 (conversations, messages)

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend Layer                       │
│  ┌──────────────┐               ┌──────────────┐            │
│  │     Web      │               │   Mobile     │            │
│  |  Clients     │               │   Clients    │            │
│  └──────┬───────┘               └──────┬───────┘            │
└─────────┼──────────────────────────────┼────────────────────┘
          │                              │
          │         HTTP/REST            │
          │                              │
┌─────────▼──────────────────────────────▼────────────────────┐
│                      API Layer (FastAPI)                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              /api/chat/message                       │   │
│  │              /api/chat/conversation/{id}/messages    │   │
│  │              /api/user/{id}/conversations            │   │
│  │              /api/chat (legacy)                      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────┬───────────────────────────────────────────────────┘
          │
          │
┌─────────▼────────────────────────────────────────────────────┐
│                   Orchestrator Layer                         │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Intent Classification (LLM-based)                   │    │
│  │  - product_detail                                    │    │
│  │  - analytics_reporting                               │    │
│  │  - ai_content_generation                             │    │
│  │  - market_intelligence                               │    │
│  │  - recommendation_engine                             │    │
│  │  - out_of_scope                                      │    │
│  └──────────────────────────────────────────────────────┘    │
└─────────┬────────────────────────────────────────────────────┘
          │
          │ Routes to Categories
          │
┌─────────▼────────────────────────────────────────────────────┐
│                    Category Handlers                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │  Product     │  │  Analytics   │  │  AI Content  │        │
│  │  Detail      │  │  Reporting   │  │  Generation  │        │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘        │ 
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────▼───────┐        │
│  │  Market      │  │Recommendation│  │  Out of      │        │
│  │ Intelligence │  │  Engine      │  │  Scope       │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
└─────────┬────────────────────────────────────────────────────┘
          │
          │
┌─────────▼────────────────────────────────────────────────────┐
│                    Service Layer                             │
│  ┌──────────────┐                                            │
│  │   Agent      │                                            │
│  │   Service    │                                            │
│  └──────┬───────┘                                            │
│  ┌──────▼───────┐  ┌──────────────┐                          │
│  │   Intent     │  │   Memory     │                          │
│  │   Extractor  │  │   Layer      │                          │
│  └──────────────┘  └──────────────┘                          │
└─────────┬────────────────────────────────────────────────────┘
          │
          │
┌─────────▼────────────────────────────────────────────────────┐
│                    External Services                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │   AWS        │  │   MongoDB    │  │   Analytics  │        │
│  │   Bedrock    │  │   Database   │  │   API        │        │ 
│  │   (LLM + KB) │  │              │  │   (External) │        │ 
│  └──────────────┘  └──────────────┘  └──────────────┘        │
└──────────────────────────────────────────────────────────────┘
```

### Component Interaction Flow

1. **User sends message** → Frontend/API receives request
2. **API validates** → Checks conversation ID, context, wallet balance
3. **Memory Layer** → Retrieves conversation history (with summaries)
4. **Orchestrator** → Classifies intent using LLM
5. **Category Handler** → Processes query based on intent
6. **LLM/KB** → Generates response using knowledge base
7. **Intent Extractor** → Extracts structured data (agent IDs, intents)
8. **Component Generator** → Creates UI components (agent cards, quick actions)
9. **Database** → Saves message and updates conversation
10. **Response** → Returns structured response to frontend

---

## Core Features & Components

### 1. Intent Classification & Orchestration

**Purpose**: Routes user queries to appropriate category handlers based on intent.

**How It Works**:
- Uses LLM (Mistral Large) to classify queries into 6 categories
- Analyzes user message + conversation history for context
- Returns category ID for routing

**Categories**:
1. **product_detail**: Platform features, pricing, capabilities, conversation memory
2. **analytics_reporting**: User's own data, metrics, reports, business health
3. **ai_content_generation**: Content generation, image analysis, optimization
4. **market_intelligence**: Market data, competitors, pricing intelligence
5. **recommendation_engine**: Recommendations, advice, improvements
6. **out_of_scope**: Non-e-commerce queries (politely declined)

**Edge Cases**:
- **Ambiguous queries**: Falls back to `product_detail` (default)
- **Context-dependent queries**: Uses conversation history to disambiguate
- **LLM classification failure**: Returns `product_detail` with error logging

**Pros**:
- ✅ Intelligent routing based on semantic understanding
- ✅ Context-aware classification
- ✅ Extensible category system

**Cons**:
- ❌ LLM classification adds latency (~200-500ms)
- ❌ Classification errors can route to wrong category
- ❌ Requires LLM API calls for every query

---

### 2. Memory Layer & Conversation Summarization

**Purpose**: Manages conversation context efficiently using intelligent summarization.

**How It Works**:
- **Messages 1-4**: Returns all messages as context
- **Message 4**: Creates summary of messages 1-4 using LLM
- **Message 8**: Creates summary of messages 5-8
- **Message 12**: Creates summary of messages 9-12
- **Pattern continues**: Every 4 messages, creates a new summary chunk
- **Context retrieval**: Returns all summaries + last 4 recent messages

**Key Functions**:
- `get_conversation_context()`: Retrieves formatted context
- `create_summary_for_chunk()`: Creates LLM-based summaries
- `summarize_messages()`: Uses LLM to extract key facts

**Edge Cases**:
- **Summary generation failure**: Falls back to raw messages (last 4)
- **Missing summaries**: Automatically creates missing summaries on retrieval
- **Empty conversation**: Returns empty context array
- **Database connection failure**: Returns empty context (graceful degradation)

**Pros**:
- ✅ Efficient context management (reduces token usage)
- ✅ Maintains long conversation history
- ✅ Automatic summarization at fixed intervals

**Cons**:
- ❌ Summary quality depends on LLM performance
- ❌ Summarization adds latency (~500-1000ms per summary)

**Potential Issues**:
- **DB Connection Failure**: Memory layer cannot retrieve history
  - **Impact**: Conversation context lost, responses lack continuity
  - **Mitigation**: Falls back to empty context, logs error
  - **Recovery**: Automatic retry on next request

---

### 3. Knowledge Base Integration

**Purpose**: Retrieves relevant information from AWS Bedrock Knowledge Base.

**How It Works**:
- Uses `AmazonKnowledgeBasesRetriever` from LangChain
- Vector search with 20 results per query
- Retrieves documents based on semantic similarity
- Formats documents for LLM context

**Configuration**:
- Knowledge Base ID: `6CKNJD5JXX` (configurable via env)
- Number of results: 20
- Retrieval method: Vector search

**Edge Cases**:
- **No results found**: Returns empty context, LLM uses training data
- **Knowledge base unavailable**: Falls back to LLM training data
- **Timeout**: Retries with exponential backoff (3 attempts)

**Pros**:
- ✅ Accurate, up-to-date information from knowledge base
- ✅ Semantic search finds relevant content
- ✅ Reduces hallucination

**Potential Issues**:
- **AWS Connection Error**: Cannot retrieve from knowledge base
  - **Impact**: Product detail queries lack accurate information
  - **Mitigation**: Retry with exponential backoff, fallback to LLM training data
  - **Recovery**: Automatic retry on next request

---

### 4. Agent Service & Caching

**Purpose**: Fetches and caches AI agent information from knowledge base.

**How It Works**:
- Queries knowledge base for agent catalog
- Uses LLM to parse agent data into structured format
- Caches agents in memory and disk (`agents_cache.json`)
- Hash-based change detection (only re-parses if KB content changes)

**Caching Strategy**:
1. **In-memory cache**: Fast access for repeated requests
2. **Disk cache**: Persists across restarts (`agents_cache.json`)
3. **Hash-based invalidation**: Compares KB content hash
4. **Fallback agents**: Hardcoded agents if KB fetch fails

**Agent Data Structure**:
```json
{
  "smart-listing": {
    "name": "Smart Listing Agent",
    "icon": "📝",
    "cost": {"INR": 30, "USD": 0.40},
    "marketplace": ["Amazon", "ONDC", "eBay"],
    "features": ["List products instantly", "AI-written titles"]
  }
}
```

**Edge Cases**:
- **KB fetch failure**: Uses cached agents from disk
- **Cache file missing**: Uses fallback hardcoded agents
- **LLM parsing failure**: Uses cached agents, logs error
- **Hash mismatch**: Re-parses agents, updates cache

**Pros**:
- ✅ Fast agent lookup (cached)
- ✅ Automatic cache invalidation on KB changes
- ✅ Resilient to KB failures (fallback agents)

**Potential Issues**:
- **KB Connection Error**: Cannot fetch agent data
  - **Impact**: Agent cards may show incorrect/outdated information
  - **Mitigation**: Uses cached agents, fallback hardcoded agents
  - **Recovery**: Automatic retry on next request

---

### 5. Currency Service

**Purpose**: Detects user currency (INR/USD) based on location.

**How It Works**:
- **Priority 1**: `loginLocation` (primary source)
  - "India" → INR
  - Others → USD
- **Priority 2**: `country` code (fallback)
  - "IN"/"IND"/"INDIA" → INR
  - Others → USD
- **Priority 3**: `timezone` (fallback)
  - India timezones → INR
  - Others → USD
- **Default**: USD if no location info

**Currency Formatting**:
- **INR**: ₹30 (no decimals)
- **USD**: $0.40 (2 decimals)

**Edge Cases**:
- **No location info**: Defaults to USD
- **Invalid country code**: Treated as non-India → USD
- **Timezone ambiguity**: Uses country code if available

**Pros**:
- ✅ Simple, deterministic logic
- ✅ Multiple fallback sources
- ✅ Fast (no external API calls)

**Cons**:
- ❌ Binary choice (INR/USD only)

---

### 6. Intent Extractor & Component Generation

**Purpose**: Extracts structured data from LLM responses and generates UI components.

**How It Works**:
1. **Intent Extraction**: Parses LLM response for intent and agentId
2. **Agent Validation**: Validates agent IDs against agent database
3. **Component Generation**: Creates agent cards, quick actions, suggested agents
4. **Currency Conversion**: Converts agent costs based on user currency

**Component Types**:
- **AgentCard**: Primary agent suggestion with cost, features, marketplace
- **SuggestedAgents**: Alternative agent recommendations
- **QuickActions**: Action buttons (top-up, launch agent, etc.)

**Edge Cases**:
- **Invalid agent ID**: Filters out invalid agents, logs warning
- **Missing agent data**: Skips component generation
- **Insufficient balance**: Generates error component with top-up action
- **Multiple agents**: Shows first valid agent as primary, others as suggestions

**Pros**:
- ✅ Automatic currency conversion
- ✅ Validates agent IDs against database

**Cons**:
- ❌ Component generation adds complexity
- ❌ Requires agent database to be up-to-date
- ❌ May generate unnecessary components

---

### 7. Database & Conversation Storage

**Purpose**: Persists conversations and messages in MongoDB.

**Collections**:
1. **conversations**: Conversation metadata, summaries, stats
2. **messages**: Individual user/assistant messages
3. **user_sessions**: User session tracking
4. **wallet_transactions**: Wallet transaction history

**Conversation Schema**:
```json
{
  "_id": "conv_abc123...",
  "userId": "user_123",
  "status": "active",
  "createdAt": "2026-01-14T12:00:00Z",
  "updatedAt": "2026-01-14T12:30:00Z",
  "lastMessageAt": "2026-01-14T12:30:00Z",
  "stats": {
    "messageCount": 10,
    "totalTokensUsed": 5000,
    "totalCost": 0.50
  },
  "conversationSummaries": [
    {
      "summary": "User asked about pricing...",
      "startIndex": 1,
      "endIndex": 4,
      "messageCount": 4,
      "createdAt": "2026-01-14T12:05:00Z"
    }
  ],
  "clientInfo": {
    "device": "desktop",
    "platform": "web",
    "timezone": "Asia/Kolkata"
  }
}
```

**Message Schema**:
```json
{
  "_id": "msg_xyz789...",
  "conversationId": "conv_abc123...",
  "userId": "user_123",
  "role": "user",
  "content": "What AI agents are available?",
  "messageType": "text",
  "timestamp": "2026-01-14T12:30:00Z",
  "metadata": {}
}
```

**Edge Cases**:
- **Duplicate conversation ID**: Creates new conversation with generated ID
- **Message save failure**: Logs error, continues without persistence
- **Database connection timeout**: Retries with exponential backoff
- **Invalid user ID format**: Validates and rejects with error

**Pros**:
- ✅ Persistent conversation history
- ✅ Supports conversation analytics
- ✅ Scalable MongoDB architecture

**Cons**:
- ❌ Database dependency (single point of failure)
- ❌ Connection overhead per request

**Potential Issues**:
- **MongoDB Connection Failure**: Cannot save/retrieve conversations
  - **Impact**: 
    - Memory layer cannot retrieve history → responses lack context
    - Messages not persisted → conversation history lost
    - Conversation stats not updated
  - **Mitigation**: 
    - Graceful degradation (continues without persistence)
    - Automatic retry on next request
    - Logs errors for monitoring
  - **Recovery**: 
    - Automatic reconnection on next request
    - Manual restart if persistent failure

---

### 8. Analytics Reporting Integration

**Purpose**: Routes analytics queries to external analytics API.

**How It Works**:
- Detects `analytics_reporting` intent
- Calls external API: `https://ai-dev.mysellercentral.com/nlp-agents/api/chat`
- Passes user_id, message, schema_name
- Returns analytics response to user

**Requirements**:
- `user_id`: Required (defaults to 48 if missing) (For testinf purpose)
- `marketplaces_registered`: Required (returns error if empty)

**Edge Cases**:
- **Missing user_id**: Uses default user_id (48), logs warning
- **Empty marketplaces**: Returns error message asking user to link marketplaces
- **API timeout**: Returns timeout error message
- **API failure**: Returns generic error message

**Pros**:
- ✅ Delegates complex analytics to specialized service
- ✅ Clean separation of concerns
- ✅ Handles analytics-specific logic externally

**Cons**:
- ❌ External API dependency (single point of failure)
- ❌ Network latency (~500-2000ms)

**Potential Issues**:
- **Analytics API Down**: Cannot process analytics queries
  - **Impact**: Users cannot get analytics data
  - **Mitigation**: Returns error message, logs for monitoring
  - **Recovery**: Automatic retry on next request, manual intervention if persistent

---

## Technical Deep Dive

### API Request Flow

```
1. User Request
   ↓
2. FastAPI receives POST /api/chat/message
   ↓
3. Validate request (conversationId, context, message)
   ↓
4. Get/Create conversation (MongoDB)
   ↓
5. Save user message (MongoDB)
   ↓
6. Memory Layer: Get conversation context
   ↓
7. Orchestrator: Classify intent (LLM)
   ↓
8. Category Handler: Process query
   ├─ Product Detail → KB retrieval + LLM
   ├─ Analytics → External API call
   ├─ AI Content → LLM generation
   ├─ Market Intelligence → LLM + KB
   ├─ Recommendation → LLM with context
   └─ Out of Scope → Polite decline
   ↓
9. Intent Extractor: Extract structured data
   ↓
10. Component Generator: Create UI components
   ↓
11. Wallet Balance Check (if agent suggested)
   ↓
12. Save assistant message (MongoDB)
   ↓
13. Return structured response
```

### LLM Integration Details

**Model**: Mistral Large 2402 v1:0
- **Provider**: AWS Bedrock
- **Max Tokens**: 1000 (configurable)
- **Temperature**: 0.1 (low for deterministic responses)
- **Region**: us-east-1 (configurable)

**Request Format**:
- **System Prompt**: Category-specific instructions
- **Messages**: Conversation history + current message
- **Context**: Knowledge base documents (for product_detail)

**Response Format**:
- **Text Response**: Natural language reply
- **Structured Data**: JSON block with intent and agentId (optional)

**Token Tracking**:
- Tracks input/output tokens per request
- Stores in message metadata
- Used for cost calculation

**Retry Logic**:
- **Retryable Errors**: 429, 500, 502, 503, 504, throttling, connection errors
- **Retry Strategy**: Exponential backoff (1s, 2s, 4s)
- **Max Attempts**: 3

**Edge Cases**:
- **LLM timeout**: Retries with exponential backoff
- **Invalid JSON in response**: Uses regex parsing fallback
- **Empty response**: Returns error message
- **Rate limiting**: Retries with backoff

**Potential Issues**:
- **AWS Bedrock Service Outage**: Cannot generate responses
  - **Impact**: All queries fail, system unusable
  - **Mitigation**: Retry with exponential backoff, return error message
  - **Recovery**: Automatic retry, manual intervention if persistent

- **Rate Limiting**: Too many requests
  - **Impact**: Requests throttled, increased latency
  - **Mitigation**: Exponential backoff, request queuing
  - **Recovery**: Automatic retry after backoff period

---

## API Documentation

### Endpoint: POST /api/chat/message

**Purpose**: Main chat endpoint for sending messages.

**Request Body**:
```json
{
  "message": "What AI agents are available?",
  "conversationId": "conv_abc123...",
  "messageType": "text",
  "context": {
    "userId": "user_123",
    "username": "John",
    "marketplaces_registered": ["Amazon", "Walmart"],
    "wallet_balance": 100.0,
    "loginLocation": "India",
    "clientInfo": {
      "device": "desktop",
      "appVersion": "1.0.0",
      "timezone": "Asia/Kolkata",
      "platform": "web",
      "country": "IN"
    }
  },
  "language": "English"
}
```

**Response (Success)**:
```json
{
  "success": true,
  "data": {
    "messageId": "msg_xyz789...",
    "reply": "Here are the available AI agents...",
    "intent": "product_detail",
    "conversationId": "conv_abc123...",
    "timestamp": "2026-01-14T12:30:00Z",
    "messageType": "text",
    "components": {
      "agentCard": {
        "agentId": "smart-listing",
        "name": "Smart Listing Agent",
        "icon": "📝",
        "cost": 30.0,
        "currency": "INR",
        "currencySymbol": "₹",
        "walletAfter": 70.0,
        "features": ["List products instantly", "AI-written titles"],
        "marketplace": ["Amazon", "ONDC", "eBay"]
      },
      "suggestedAgents": [],
      "quickActions": []
    },
    "walletBalance": 100.0
  },
  "metadata": {
    "modelVersion": "mistral.mistral-large-2402-v1:0",
    "tokensUsed": 500,
    "inputTokens": 300,
    "outputTokens": 200,
    "latencyMs": 1250.5,
    "requestId": "req_abc123..."
  }
}
```

**Response (Error)**:
```json
{
  "success": false,
  "error": {
    "code": "INSUFFICIENT_BALANCE",
    "message": "Insufficient balance John. You need ₹30 to use this agent.",
    "details": {
      "required": 30.0,
      "current": 10.0,
      "shortfall": 20.0
    },
    "walletBalance": 10.0,
    "components": {
      "quickActions": [
        {
          "label": "Click here to Top-up",
          "url": "https://mysellercentral.com/ai-agents/",
          "actionType": "url"
        }
      ]
    }
  }
}
```

**Error Codes**:
- `INSUFFICIENT_BALANCE`: User doesn't have enough wallet balance
- `AGENT_UNAVAILABLE`: Requested agent is not available
- `INVALID_CONVERSATION`: Conversation ID is invalid
- `RATE_LIMIT_EXCEEDED`: Too many requests
- `INTERNAL_ERROR`: Unexpected server error
- `VALIDATION_ERROR`: Request validation failed
- `KNOWLEDGE_BASE_ERROR`: Knowledge base retrieval failed
- `MODEL_ERROR`: LLM generation failed

**Edge Cases**:
- **Empty conversationId**: Creates new conversation
- **Invalid conversationId**: Creates new conversation
- **Missing context**: Returns validation error
- **Invalid messageType**: Defaults to "text"

---

### Endpoint: GET /api/chat/conversation/{conversation_id}/messages

**Purpose**: Retrieve all messages for a conversation.

**Response**:
```json
{
  "success": true,
  "data": {
    "conversationId": "conv_abc123...",
    "conversation": {
      "_id": "conv_abc123...",
      "userId": "user_123",
      "status": "active",
      "stats": {
        "messageCount": 10
      }
    },
    "messages": [
      {
        "_id": "msg_001",
        "role": "user",
        "content": "What AI agents are available?",
        "timestamp": "2026-01-14T12:00:00Z"
      },
      {
        "_id": "msg_002",
        "role": "assistant",
        "content": "Here are the available AI agents...",
        "timestamp": "2026-01-14T12:00:05Z"
      }
    ],
    "messageCount": 10
  },
  "requestId": "req_xyz789..."
}
```

**Edge Cases**:
- **Conversation not found**: Returns empty messages array
- **Database error**: Returns 500 error
- **Invalid conversation_id format**: Returns validation error

---

### Endpoint: GET /api/user/{user_id}/conversations

**Purpose**: Retrieve all conversations for a user.

**Query Parameters**:
- `include_messages`: boolean (default: true)
- `limit`: integer (default: 50)
- `skip`: integer (default: 0)

**Response**:
```json
{
  "success": true,
  "data": {
    "userId": "user_123",
    "conversations": [
      {
        "conversationId": "conv_abc123...",
        "userId": "user_123",
        "status": "active",
        "title": "AI Agents Discussion",
        "createdAt": "2026-01-14T12:00:00Z",
        "updatedAt": "2026-01-14T12:30:00Z",
        "lastMessageAt": "2026-01-14T12:30:00Z",
        "stats": {
          "messageCount": 10
        },
        "messages": [...],
        "messageCount": 10
      }
    ],
    "totalConversations": 1
  },
  "requestId": "req_xyz789..."
}
```

**Edge Cases**:
- **User not found**: Returns empty conversations array
- **Pagination**: Uses limit/skip for large result sets
- **Database error**: Returns 500 error

---

## Database Schema

### Conversations Collection

**Purpose**: Stores conversation metadata, summaries, and statistics.

**Schema**:
```json
{
  "_id": "conv_[16 hex chars]",
  "userId": "user_[alphanumeric_underscore]",
  "status": "active" | "archived" | "deleted",
  "title": "string (optional)",
  "createdAt": "ISO 8601 datetime",
  "updatedAt": "ISO 8601 datetime",
  "lastMessageAt": "ISO 8601 datetime",
  "stats": {
    "messageCount": "integer",
    "totalTokensUsed": "integer",
    "totalCost": "float"
  },
  "conversationSummaries": [
    {
      "summary": "string",
      "startIndex": "integer (1-based)",
      "endIndex": "integer (1-based)",
      "messageCount": "integer",
      "createdAt": "ISO 8601 datetime"
    }
  ],
  "clientInfo": {
    "device": "mobile" | "desktop" | "tablet",
    "appVersion": "string",
    "timezone": "string",
    "platform": "ios" | "android" | "web",
    "userAgent": "string",
    "country": "string"
  },
  "metadata": {}
}
```

**Indexes**:
- `_id`: Primary key
- `userId`: For user conversation queries
- `lastMessageAt`: For sorting conversations

**Edge Cases**:
- **Missing required fields**: Validation error on insert
- **Invalid userId format**: Rejected by validation
- **Duplicate _id**: MongoDB error (shouldn't happen with generated IDs)

---

### Messages Collection

**Purpose**: Stores individual user and assistant messages.

**Schema**:
```json
{
  "_id": "msg_[12 hex chars]",
  "conversationId": "conv_[16 hex chars]",
  "userId": "user_[alphanumeric_underscore]",
  "role": "user" | "assistant",
  "content": "string",
  "messageType": "text" | "voice" | "image",
  "timestamp": "ISO 8601 datetime",
  "intent": "string (optional)",
  "assistantResponse": {
    "intent": "string"
  },
  "agentCard": {
    "agentId": "string",
    "name": "string",
    "cost": "float",
    ...
  },
  "suggestedAgents": [],
  "quickActions": [],
  "processing": {
    "modelVersion": "string",
    "latencyMs": "float",
    "tokensUsed": "integer",
    "inputTokens": "integer",
    "outputTokens": "integer"
  },
  "metadata": {}
}
```

**Indexes**:
- `_id`: Primary key
- `conversationId`: For conversation message queries
- `userId`: For user message queries
- `timestamp`: For sorting messages

**Edge Cases**:
- **Missing conversationId**: Validation error
- **Invalid role**: Must be "user" or "assistant"
- **Large content**: MongoDB document size limit (16MB)

---

## Memory Management

### Summarization Strategy

**Chunk Size**: 4 messages per summary

**Summary Creation**:
- **Message 4**: Summarizes messages 1-4
- **Message 8**: Summarizes messages 5-8
- **Message 12**: Summarizes messages 9-12
- **Pattern**: Every 4 messages, create new summary

**Context Retrieval**:
- **Messages 1-4**: Returns all messages
- **Messages 5-8**: Returns summary(1-4) + messages 5-8
- **Messages 9-12**: Returns summary(1-4) + summary(5-8) + messages 9-12
- **Messages 13+**: Returns all summaries + last 4 messages

**Summary Format**:
```
[Previous conversation summary (messages 1-4)]: User asked about pricing plans. 
Discussed Silver plan features. User mentioned they have 50 products on Amazon.
```

**LLM Summarization Prompt**:
- Focuses on key facts, numbers, metrics
- Preserves user context, goals, pain points
- Extracts specific details (products, marketplaces, challenges)

**Edge Cases**:
- **Summary generation failure**: Falls back to raw messages (last 4)
- **Missing summaries**: Automatically creates on retrieval
- **Incomplete chunks**: Waits until chunk is complete (multiple of 4)
- **Summary quality issues**: May lose nuanced details

**Pros**:
- ✅ Efficient token usage (summaries are shorter)
- ✅ Maintains long conversation history
- ✅ Automatic summarization

**Cons**:
- ❌ Summary quality depends on LLM
- ❌ Summarization latency (~500-1000ms)
- ❌ May lose important details

**Potential Issues**:
- **LLM Summarization Failure**: Cannot create summaries
  - **Impact**: Context retrieval falls back to raw messages (may exceed token limits)
  - **Mitigation**: Falls back to last 4 messages, logs error
  - **Recovery**: Automatic retry on next summary creation

---

## Orchestrator & Intent Classification

### Classification Process

1. **Input**: User message + conversation history (last 3 messages)
2. **LLM Classification**: Mistral Large classifies into 6 categories
3. **JSON Parsing**: Extracts category from LLM response
4. **Validation**: Ensures category is valid
5. **Routing**: Routes to appropriate category handler

### Classification Prompt

The orchestrator uses a detailed prompt with:
- Category definitions and examples
- Key distinctions between categories
- Context-aware classification rules
- Edge case handling instructions

**Key Distinctions**:
- **product_detail vs analytics_reporting**:
  - product_detail: Questions about platform capabilities
  - analytics_reporting: Questions about user's own data
- **conversation memory vs analytics**:
  - "What did I tell you?" → product_detail (conversation memory)
  - "What are my sales?" → analytics_reporting (actual data)
- **analytics_reporting vs recommendation_engine**:
  - "Show me my sales" → analytics_reporting (view data)
  - "How can I improve?" → recommendation_engine (advice)

**Edge Cases**:
- **Ambiguous queries**: Falls back to product_detail
- **LLM classification failure**: Returns product_detail with error logging
- **Invalid category**: Validates and falls back to product_detail
- **Context-dependent queries**: Uses conversation history for disambiguation

**Pros**:
- ✅ Intelligent semantic classification
- ✅ Context-aware routing
- ✅ Extensible category system

**Cons**:
- ❌ Classification latency (~200-500ms)
- ❌ Classification errors possible
- ❌ Requires LLM call for every query

**Potential Issues**:
- **LLM Classification Failure**: Cannot classify intent
  - **Impact**: Routes to wrong category, incorrect responses
  - **Mitigation**: Falls back to product_detail, logs error
  - **Recovery**: Automatic retry on next request

---

## Category Handlers

### 1. ProductDetailCategory

**Purpose**: Handles queries about platform features, pricing, AI agents, marketplace integrations.

**How It Works**:
1. Retrieves documents from knowledge base
2. Formats system prompt with KB context
3. Invokes LLM with conversation history
4. Parses structured response (intent, agentId)
5. Returns cleaned response text

**System Prompt Features**:
- Personalization (username)
- Conversation memory instructions
- Knowledge base usage guidelines
- Response style guidelines
- Structured output requirements

**Edge Cases**:
- **KB retrieval failure**: Uses empty context, LLM uses training data
- **LLM timeout**: Retries with exponential backoff
- **Invalid JSON in response**: Uses regex parsing fallback
- **Empty response**: Returns error message

**Pros**:
- ✅ Accurate information from knowledge base
- ✅ Personalized responses
- ✅ Conversation memory support

**Cons**:
- ❌ KB retrieval latency
- ❌ LLM generation latency
- ❌ Dependency on KB quality

---

### 2. AnalyticsReportingCategory

**Purpose**: Routes analytics queries to external analytics API.

**How It Works**:
1. Validates user_id and marketplaces_registered
2. Calls external analytics API
3. Returns API response to user

**Requirements**:
- `user_id`: Required
- `marketplaces_registered`: Required (non-empty list)

**Edge Cases**:
- **Missing user_id**: Uses default (48), logs warni
- **Empty marketplaces**: Returns error asking user to link marketplaces
- **API timeout**: Returns timeout error
- **API failure**: Returns generic error

**Pros**:
- ✅ Delegates to specialized service
- ✅ Clean separation of concerns

**Cons**:
- ❌ External API dependency
- ❌ Network latency


---

### 3. AIContentGenerationCategory (WIP)

**Purpose**: Handles AI-driven content generation tasks.

**Capabilities**:
- Content generation (titles, descriptions, A+ content)
- Image analysis
- Product intelligence
- Text optimization

**Edge Cases**:
- **Unsupported task**: Returns error message
- **LLM generation failure**: Returns error with retry suggestion

---

### 4. MarketIntelligenceCategory (WIP)

**Purpose**: Handles market data, competitor analysis, pricing intelligence queries.

**Capabilities**:
- Market data queries
- Competitor analysis
- Pricing intelligence
- Best practices

**Edge Cases**:
- **No market data available**: Returns "data not available" message
- **LLM generation failure**: Returns error

---

### 5. RecommendationEngineCategory

**Purpose**: Provides recommendations and advice based on conversation context.

**How It Works**:
- Uses conversation history for context
- Generates recommendations using LLM
- Provides actionable advice

**Edge Cases**:
- **No context**: Asks clarifying questions
- **LLM generation failure**: Returns error

---

### 6. OutOfScopeCategory

**Purpose**: Handles non-e-commerce queries with polite decline.

**Response Style**:
- Polite decline message
- Redirects to e-commerce topics
- Maintains friendly tone

**Edge Cases**:
- **Borderline queries**: May misclassify (handled by orchestrator)

---

## Services & Utilities

### AgentService

**Purpose**: Fetches and caches agent information.

**Key Methods**:
- `get_all_agents()`: Returns all agents (with caching)
- `get_agent_by_id()`: Returns specific agent
- `invalidate_cache()`: Clears cache

**Caching**:
- In-memory cache
- Disk cache (`agents_cache.json`)
- Hash-based invalidation

---

### CurrencyService

**Purpose**: Detects and formats currency.

**Key Methods**:
- `detect_currency()`: Detects INR/USD based on location
- `format_currency()`: Formats amount with symbol
- `get_currency_symbol()`: Returns currency symbol

---

### IntentExtractor

**Purpose**: Extracts intent and generates UI components.

**Key Methods**:
- `extract_intent()`: Extracts intent and agentId
- `generate_components()`: Creates UI components
- `_extract_agent_from_text()`: Extracts agent from text

---

## Edge Cases & Error Handling

### 1. Database Connection Failures

**Scenario**: MongoDB is unavailable or connection times out.

**Impact**:
- Memory layer cannot retrieve conversation history
- Messages cannot be saved
- Conversation stats not updated

**Handling**:
- Graceful degradation (continues without persistence)
- Automatic retry on next request
- Error logging for monitoring

**Recovery**:
- Automatic reconnection on next request
- Manual restart if persistent failure

---

### 2. AWS Bedrock Service Outages

**Scenario**: AWS Bedrock is unavailable or rate-limited.

**Impact**:
- All LLM operations fail
- Intent classification fails
- Response generation fails

**Handling**:
- Retry with exponential backoff (3 attempts)
- Returns error message to user
- Logs errors for monitoring

**Recovery**:
- Automatic retry after backoff
- Manual intervention if persistent

---

### 3. Knowledge Base Retrieval Failures

**Scenario**: Knowledge base is unavailable or returns no results.

**Impact**:
- Product detail queries lack accurate information
- LLM uses training data (may be outdated)

**Handling**:
- Retry with exponential backoff
- Falls back to LLM training data
- Logs warnings

**Recovery**:
- Automatic retry on next request
- Manual KB investigation if persistent

---

### 4. Analytics API Failures

**Scenario**: External analytics API is down or times out.

**Impact**:
- Users cannot get analytics data
- Analytics queries fail

**Handling**:
- Returns error message to user
- Logs errors for monitoring
- Timeout handling (30s timeout)

**Recovery**:
- Automatic retry on next request
- Manual intervention if persistent


---

### 5. Insufficient Wallet Balance

**Scenario**: User doesn't have enough balance for suggested agent.

**Impact**:
- Agent cannot be used
- User sees error message

**Handling**:
- Checks balance before returning agent card
- Returns error with top-up quick action
- Prevents agent launch

**Recovery**:
- User tops up wallet
- Retries agent launch after top-up

---

### 6. Conversation Memory Failures

**Scenario**: Memory layer cannot retrieve or create summaries.

**Impact**:
- Responses lack conversation context
- User experience degrades

**Handling**:
- Falls back to last 4 messages
- Logs errors
- Continues without full context

**Recovery**:
- Automatic retry on next request
- Manual investigation if persistent

---

### 7. LLM Response Parsing Failures

**Scenario**: LLM returns invalid JSON or malformed structured data.

**Impact**:
- Intent extraction may fail
- Agent IDs may not be extracted

**Handling**:
- Multiple regex parsing strategies
- Falls back to keyword matching
- Logs warnings

**Recovery**:
- Uses fallback intent extraction
- Skips component generation if needed

---

## Potential Issues & Failure Points

### Critical Failure Points

#### 1. MongoDB Connection Failure

**Stage**: Database operations (memory layer, message storage)

**Impact**:
- **Memory Layer**: Cannot retrieve conversation history → responses lack context
- **Message Storage**: Messages not persisted → conversation history lost
- **Conversation Stats**: Stats not updated → analytics incomplete

**Symptoms**:
- Error logs: "MongoDB error..."
- Empty conversation context
- Messages not saved

**Mitigation**:
- Connection pooling
- Automatic retry with exponential backoff
- Graceful degradation (continues without persistence)

**Recovery**:
- Automatic reconnection on next request
- Manual restart if persistent
- Database health monitoring

---

#### 2. AWS Bedrock Service Outage

**Stage**: LLM operations (intent classification, response generation)

**Impact**:
- **Intent Classification**: Cannot classify queries → routes to default category
- **Response Generation**: Cannot generate responses → system unusable
- **Summarization**: Cannot create summaries → context management fails

**Symptoms**:
- Error logs: "Error invoking Bedrock..."
- Timeout errors
- 503/500 errors from Bedrock

**Mitigation**:
- Retry with exponential backoff (3 attempts)
- Error messages to users
- Fallback to cached responses (if available)

**Recovery**:
- Automatic retry after backoff
- Manual intervention if persistent
- AWS status monitoring

---

#### 3. Knowledge Base Retrieval Failure

**Stage**: Product detail queries

**Impact**:
- **Product Detail Queries**: Lack accurate information → LLM uses outdated training data
- **Agent Information**: Agent data may be outdated → incorrect agent cards

**Symptoms**:
- Empty context in responses
- Warnings: "Knowledge base retrieval failed"
- Inaccurate product information

**Mitigation**:
- Retry with exponential backoff
- Fallback to LLM training data
- Cached agent data (AgentService)

**Recovery**:
- Automatic retry on next request
- Manual KB investigation if persistent
- KB health monitoring

---

#### 4. Analytics API Failure

**Stage**: Analytics reporting queries

**Impact**:
- **Analytics Queries**: Cannot process → users cannot get analytics data
- **User Experience**: Poor experience for analytics users

**Symptoms**:
- Timeout errors (30s timeout)
- HTTP errors from analytics API
- Error messages to users

**Mitigation**:
- Timeout handling (30s)
- Error messages to users
- Logging for monitoring

**Recovery**:
- Automatic retry on next request
- Manual intervention if persistent
- Analytics API health monitoring

---

### Moderate Failure Points

#### 5. Agent Service Cache Failure

**Stage**: Agent information retrieval

**Impact**:
- **Agent Cards**: May show incorrect/outdated information
- **Component Generation**: May fail if agents not available

**Symptoms**:
- Warnings: "Agent cache miss"
- Fallback to hardcoded agents
- Outdated agent information

**Mitigation**:
- Disk cache fallback
- Hardcoded fallback agents
- Automatic cache refresh

**Recovery**:
- Automatic cache refresh on next request
- Manual cache invalidation if needed

---

#### 6. Memory Layer Summarization Failure

**Stage**: Conversation context retrieval

**Impact**:
- **Context Retrieval**: Falls back to raw messages → may exceed token limits
- **Long Conversations**: Context management degrades

**Symptoms**:
- Warnings: "Summary generation failed"
- Falls back to last 4 messages
- Increased token usage

**Mitigation**:
- Falls back to last 4 messages
- Error logging
- Automatic retry on next summary creation

**Recovery**:
- Automatic retry on next summary creation
- Manual investigation if persistent

---

#### 7. Intent Classification Errors

**Stage**: Orchestrator classification

**Impact**:
- **Wrong Category**: Routes to incorrect category → incorrect responses
- **User Experience**: Confusing responses

**Symptoms**:
- Incorrect category classification
- Wrong category handler invoked
- Logs: "Invalid intent returned by LLM"

**Mitigation**:
- Falls back to product_detail
- Error logging
- Classification prompt improvements

**Recovery**:
- Automatic fallback to product_detail
- Manual prompt tuning if persistent

---

### Low-Impact Failure Points

#### 8. Currency Detection Failure

**Stage**: Currency service

**Impact**:
- **Currency Formatting**: Defaults to USD → incorrect currency display
- **Agent Costs**: May show wrong currency

**Symptoms**:
- Defaults to USD
- Warnings: "No location information provided"

**Mitigation**:
- Defaults to USD (safe fallback)
- Multiple fallback sources (country, timezone)

**Recovery**:
- Automatic on next request with location info
- Manual currency override if needed

---

#### 9. Component Generation Failure

**Stage**: Intent extractor

**Impact**:
- **UI Components**: May not be generated → plain text responses
- **User Experience**: Less rich UI

**Symptoms**:
- No agent cards generated
- Warnings: "Component generation failed"

**Mitigation**:
- Falls back to plain text responses
- Error logging
- Validates agent IDs before generation

**Recovery**:
- Automatic on next request
- Manual component debugging if persistent

---

## Pros & Cons Analysis

### System Architecture

**Pros**:
- ✅ **Modular Design**: Clear separation of concerns (orchestrator, categories, services)
- ✅ **Extensible**: Easy to add new categories and features
- ✅ **Scalable**: FastAPI supports async operations, MongoDB scales horizontally
- ✅ **Resilient**: Multiple fallback mechanisms, graceful degradation
- ✅ **Maintainable**: Well-organized code structure, comprehensive logging

**Cons**:
- ❌ **Complexity**: Many moving parts, requires understanding of multiple systems
- ❌ **Dependencies**: Multiple external dependencies (AWS, MongoDB, Analytics API)
- ❌ **Latency**: Multiple API calls per request (LLM, KB, DB)
- ❌ **Cost**: LLM API calls, KB retrievals, database operations
- ❌ **Single Points of Failure**: MongoDB, AWS Bedrock, other microservices

---

### Intent Classification

**Pros**:
- ✅ **Intelligent Routing**: Semantic understanding, context-aware
- ✅ **Accurate**: LLM-based classification is more accurate than keyword matching
- ✅ **Flexible**: Handles ambiguous queries, context-dependent classification

**Cons**:
- ❌ **Latency**: Adds ~200-500ms per request
- ❌ **Cost**: LLM API call for every query
- ❌ **Errors**: Classification mistakes can route to wrong category
- ❌ **Complexity**: Requires detailed prompt engineering

---

### Memory Management

**Pros**:
- ✅ **Efficient**: Summaries reduce token usage
- ✅ **Scalable**: Handles long conversations without token limit issues
- ✅ **Automatic**: Summarization happens automatically

**Cons**:
- ❌ **Quality**: Summary quality depends on LLM
- ❌ **Latency**: Summarization adds ~500-1000ms per summary
- ❌ **Loss**: May lose nuanced details in summarization
- ❌ **Complexity**: Summary management adds complexity

---

### Knowledge Base Integration

**Pros**:
- ✅ **Accurate**: Up-to-date information from knowledge base
- ✅ **Semantic Search**: Finds relevant content based on meaning
- ✅ **Reduces Hallucination**: LLM uses KB content instead of training data

**Cons**:
- ❌ **Latency**: Retrieval adds ~300-800ms
- ❌ **Cost**: KB retrieval operations cost money
- ❌ **Dependency**: Requires AWS Bedrock Knowledge Base setup
- ❌ **Quality**: Depends on KB content quality

---

### Database Design

**Pros**:
- ✅ **Persistent**: Conversation history persists across sessions
- ✅ **Scalable**: MongoDB scales horizontally
- ✅ **Flexible**: Schema-less design allows flexibility
- ✅ **Analytics**: Supports conversation analytics

**Cons**:
- ❌ **Dependency**: Single point of failure
- ❌ **Latency**: Database operations add latency
- ❌ **Cost**: Database infrastructure costs
- ❌ **Complexity**: Connection management, error handling

---

### API Design

**Pros**:
- ✅ **Structured**: Consistent request/response format
- ✅ **Rich Components**: UI components enhance user experience
- ✅ **Error Handling**: Comprehensive error codes and messages
- ✅ **Documentation**: OpenAPI/Swagger documentation

**Cons**:
- ❌ **Complexity**: Complex request/response structures
- ❌ **Versioning**: Breaking changes require versioning
- ❌ **Validation**: Extensive validation logic

---

## Deployment & Operations

### Environment Variables

**Required**:
- `AWS_ACCESS_KEY_ID`: AWS access key
- `AWS_SECRET_ACCESS_KEY`: AWS secret key
- `AWS_DEFAULT_REGION`: AWS region (default: us-east-1)
- `BEDROCK_KNOWLEDGE_BASE_ID`: Knowledge base ID (default: 6CKNJD5JXX)
- `MONGODB_URI`: MongoDB connection string

**Optional**:
- `BEDROCK_MODEL_ID`: LLM model ID (default: mistral.mistral-large-2402-v1:0)
- `MONGODB_DATABASE`: Database name (default: msc-chatbot)
- `WALLET_SERVICE_URL`: Wallet microservice URL
- `ENVIRONMENT`: Environment (development/production)

---

### Logging

**Log Location**: `logs/` directory

**Log Format**: Timestamp, level, module, message

**Log Levels**:
- `DEBUG`: Detailed debugging information
- `INFO`: General information
- `WARNING`: Warning messages
- `ERROR`: Error messages
- `CRITICAL`: Critical errors

**Log Rotation**: Daily log files

---

### Monitoring

**Key Metrics**:
- Request latency (p50, p95, p99)
- Error rates by endpoint
- LLM token usage
- Database connection pool usage
- Memory layer summary creation success rate
- Intent classification accuracy

**Health Checks**:
- `/health`: Basic health check
- `/`: API status and endpoints

---

### Scaling Considerations

**Horizontal Scaling**:
- FastAPI supports multiple workers
- MongoDB scales horizontally
- Stateless API design (except in-memory caches)

**Vertical Scaling**:
- Increase worker count
- Increase database connection pool
- Increase memory for caching

**Bottlenecks**:
- LLM API rate limits
- Database connection pool
- Memory layer summarization (CPU-intensive)

---

## New Joiner Guide

### Getting Started

**Step 1: Understand the System**
1. Read this documentation (you're doing it!)
2. Review the README.md
3. Explore the codebase structure

**Step 2: Set Up Development Environment**
1. Install Python 3.8+
2. Create virtual environment
3. Install dependencies: `pip install -r requirements.txt`
4. Set up `.env` file with required variables
5. Set up MongoDB (local or cloud)

**Step 3: Run the System**
1. Start MongoDB (if local)
2. Run API: `python main.py`
3. Test API: `curl http://localhost:8502/health`
4. Run Streamlit: `streamlit run src/app.py`

**Step 4: Explore the Code**
1. Start with `src/api/routes.py` (API endpoints)
2. Review `src/core/orchestrator/user_intent.py` (orchestrator)
3. Check `src/categories/` (category handlers)
4. Explore `src/services/` (services)

---

### Key Concepts to Understand

**1. Orchestrator Pattern**
- Routes queries to appropriate handlers
- Uses LLM for intent classification
- Located in `src/core/orchestrator/user_intent.py`

**2. Category Handlers**
- Each category handles specific query types
- Inherits from `BaseCategory`
- Located in `src/categories/`

**3. Memory Layer**
- Manages conversation context
- Creates summaries every 4 messages
- Located in `src/core/memory_layer.py`

**4. Services**
- AgentService: Agent information
- CurrencyService: Currency detection
- IntentExtractor: Component generation
- Located in `src/services/`

---

### Common Tasks

**Adding a New Category**:
1. Create new file in `src/categories/`
2. Inherit from `BaseCategory`
3. Implement `process_query()` and `can_handle()`
4. Register in `Orchestrator.__init__()`

**Adding a New API Endpoint**:
1. Add route in `src/api/routes.py`
2. Define request/response models in `src/core/models.py`
3. Implement handler function
4. Add to OpenAPI documentation

**Modifying Intent Classification**:
1. Edit classification prompt in `Orchestrator.find_user_intent()`
2. Test with various queries
3. Monitor classification accuracy

**Debugging Issues**:
1. Check logs in `logs/` directory
2. Enable DEBUG logging
3. Use API health checks
4. Test individual components

---

### Testing

**Unit Tests**:
- Located in `tests/`
- Run: `python -m pytest tests/`

**Integration Tests**:
- Test API endpoints
- Test database operations
- Test LLM integrations

**Manual Testing**:
- Use Streamlit UI
- Use curl commands (see `docs/CURL_EXAMPLES.md`)
- Use Postman collection

---

### Troubleshooting

**Common Issues**:

1. **MongoDB Connection Error**
   - Check `MONGODB_URI` in `.env`
   - Verify MongoDB is running
   - Check network connectivity

2. **AWS Bedrock Error**
   - Check AWS credentials
   - Verify Bedrock access
   - Check region configuration

3. **Knowledge Base Error**
   - Verify `BEDROCK_KNOWLEDGE_BASE_ID`
   - Check KB permissions
   - Verify KB is accessible

4. **Import Errors**
   - Check Python path
   - Verify virtual environment is activated
   - Check `sys.path` modifications

---

## Conclusion

This comprehensive documentation covers:

- ✅ **Technical Architecture**: System design, components, interactions
- ✅ **Feature Documentation**: All features with edge cases
- ✅ **API Documentation**: Complete API reference
- ✅ **Database Schema**: Data models and relationships
- ✅ **Error Handling**: Edge cases and failure points
- ✅ **Potential Issues**: Failure points with mitigation strategies
- ✅ **Pros & Cons**: Balanced analysis of design decisions
- ✅ **New Joiner Guide**: Onboarding guide for new team members

**Key Takeaways**:
- System is modular, extensible, and resilient
- Multiple fallback mechanisms ensure graceful degradation
- Comprehensive error handling and logging
- Well-documented for maintainability

**Areas for Improvement**:
- Reduce latency (caching, optimization)
- Improve error recovery (automatic retries)
- Enhance monitoring (metrics, alerts)
- Optimize costs (caching, rate limiting)

---

