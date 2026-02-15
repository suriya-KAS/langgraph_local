# Database Schema Documentation
## MySellerCentral Chatbot - NoSQL Database Design

**Version:** 1.0  
**Date:** December 2024  
**Database:** MongoDB (NoSQL)

---

## 📋 Executive Summary

This document outlines the database schema design for the MySellerCentral Chatbot application. The system uses MongoDB to store conversations, messages, user sessions, and wallet transactions. The schema is optimized for:

- **Performance**: Fast retrieval of conversation history and messages
- **Scalability**: Efficient handling of large conversation volumes
- **Cost Optimization**: Context window management through message summarization
- **Data Integrity**: Schema validation and unique constraints

---

## 🗂️ Collections Overview

| Collection | Purpose | Key Features |
|------------|---------|--------------|
| **conversations** | Store conversation metadata and recent messages | FIFO queue for last 10 messages, conversation summarization |
| **messages** | Store all individual messages | Full message history with metadata, 90-day TTL |
| **user_sessions** | Track user session activity | Session analytics, 180-day TTL |
| **wallet_transactions** | Record wallet balance transactions | Transaction history, strict validation |

---

## 1️⃣ Conversations Collection

### Purpose
Stores conversation-level metadata, recent messages (last 10), and conversation summaries for efficient context window management.

### Key Features
- ✅ FIFO queue for recent messages (last 10)
- ✅ Conversation summarization for cost optimization
- ✅ Status tracking (active, archived, deleted)
- ✅ Auto-archival via TTL index

### Schema Structure

#### Required Fields

| Field | Type | Pattern/Values | Description |
|-------|------|---------------|-------------|
| `_id` | string | `conv_[16-char-hex]` | Unique conversation identifier |
| `userId` | string | `user_[alphanumeric]` | User identifier |
| `status` | enum | `active`, `archived`, `deleted` | Conversation status |
| `createdAt` | date | - | Creation timestamp |
| `updatedAt` | date | - | Last update timestamp |
| `lastMessageAt` | date | - | Last message timestamp |

#### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `title` | string (max 200) | Auto-generated or user-set conversation title |
| `recentMessages` | array (max 10) | Last 10 messages for quick context retrieval |
| `conversationSummary` | object | Summarized content of older messages |
| `stats` | object | Conversation statistics |
| `expiresAt` | date | Expiration timestamp for TTL-based archival |
| `metadata` | object | Source, satisfaction rating, feedback |
| `clientInfo` | object | Device, platform, timezone information |

#### Recent Messages Structure

Each message in `recentMessages` array contains:

| Field | Type | Description |
|-------|------|-------------|
| `messageId` | string | Unique message identifier |
| `role` | enum | `user`, `assistant`, `system` |
| `content` | string (max 5000) | Message content |
| `timestamp` | date | Message timestamp |
| `intent` | string/null | Detected intent (for assistant messages) |
| `agentId` | string/null | Agent ID if agent was suggested |

#### Conversation Summary Structure

| Field | Type | Description |
|-------|------|-------------|
| `content` | string (max 5000) | Summarized content of older messages |
| `messageCount` | int | Number of messages that were summarized |
| `lastUpdated` | date | When summary was last created/updated |

#### Statistics Structure

| Field | Type | Description |
|-------|------|-------------|
| `messageCount` | int | Total number of messages in conversation |
| `totalTokensUsed` | int | Total tokens consumed |
| `totalCost` | double | Total cost in tokens/currency |

#### Metadata Structure

| Field | Type | Description |
|-------|------|-------------|
| `source` | enum | `web`, `mobile`, `api` |
| `satisfactionRating` | int/null | User satisfaction rating (1-5) |
| `feedback` | string/null | User feedback text (max 1000 chars) |

#### Client Info Structure

| Field | Type | Description |
|-------|------|-------------|
| `device` | enum | `mobile`, `desktop`, `tablet` |
| `appVersion` | string | Application version |
| `platform` | enum | `ios`, `android`, `web`, null |
| `timezone` | string | User timezone (e.g., Asia/Kolkata) |

### Indexes

| Index Name | Fields | Purpose |
|------------|--------|---------|
| `idx_userId_lastMessageAt` | `userId`, `lastMessageAt` (desc) | Get user's conversations ordered by activity |
| `idx_userId_status_lastMessageAt` | `userId`, `status`, `lastMessageAt` (desc) | Filter by user and status |
| `idx_status_updatedAt` | `status`, `updatedAt` (desc) | Global conversation listing (admin/analytics) |
| `idx_expiresAt_ttl` | `expiresAt` | Auto-archival of expired conversations |
| `idx_tags_updatedAt` | `metadata.tags`, `updatedAt` (desc) | Search by tags (sparse) |
| `idx_createdAt` | `createdAt` (desc) | Find conversations by creation date |

### Use Cases

1. **Quick Context Retrieval**: Fetch last 10 messages for LLM context
2. **Cost Optimization**: Use conversation summary + recent messages instead of full history
3. **User Experience**: Display conversation list sorted by last activity
4. **Analytics**: Track conversation metrics and user satisfaction

---

## 2️⃣ Messages Collection

### Purpose
Stores all individual messages with full metadata, supporting complete conversation history and analytics.

### Key Features
- ✅ Complete message history (not limited to 10)
- ✅ Rich metadata (processing info, components, errors)
- ✅ 90-day TTL for automatic cleanup
- ✅ Support for multiple message types (text, voice, image)

### Schema Structure

#### Required Fields

| Field | Type | Pattern/Values | Description |
|-------|------|---------------|-------------|
| `_id` | string | `msg_[hex]` | Unique message identifier |
| `conversationId` | string | `conv_[16-char-hex]` | Reference to conversation |
| `userId` | string | `user_[alphanumeric]` | User identifier |
| `role` | enum | `user`, `assistant`, `system` | Message sender role |
| `content` | string | - | Message content |
| `timestamp` | date | - | Message timestamp |
| `createdAt` | date | - | Creation timestamp |

#### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `messageType` | enum | `text`, `voice`, `image` |
| `userRequest` | object | Original user request data |
| `assistantResponse` | object | Assistant response metadata |
| `agentCard` | object | Agent card component |
| `suggestedAgents` | array | Alternative agent suggestions |
| `quickActions` | array | Quick action buttons |
| `media` | array | Media attachments |
| `processing` | object | Processing metadata |
| `error` | object | Error information |

#### Processing Structure

| Field | Type | Description |
|-------|------|-------------|
| `modelVersion` | string | AI model version used |
| `tokensUsed` | int/null | Tokens consumed |
| `latencyMs` | double/null | Response latency in milliseconds |
| `requestId` | string/null | Request ID for tracing |

#### Error Structure

| Field | Type | Description |
|-------|------|-------------|
| `code` | string/null | Error code |
| `message` | string/null | Error message |
| `timestamp` | date/null | Error timestamp |

### Indexes

| Index Name | Fields | Purpose |
|------------|--------|---------|
| `idx_conversationId_timestamp` | `conversationId`, `timestamp` (asc) | Get messages for a conversation chronologically |
| `idx_userId_timestamp` | `userId`, `timestamp` (desc) | Get messages by user across all conversations |
| `idx_intent_timestamp` | `assistantResponse.intent`, `timestamp` (desc) | Find messages by intent (analytics) |
| `idx_agentId_timestamp` | `agentCard.agentId`, `timestamp` (desc) | Find messages by agent (analytics) |
| `idx_error_code` | `error.code` | Find error messages (sparse) |
| `idx_timestamp_ttl` | `timestamp` | Auto-delete after 90 days |

### Use Cases

1. **Full History**: Retrieve complete conversation history for analysis
2. **Analytics**: Analyze user intents, agent usage, error patterns
3. **Debugging**: Trace requests using `requestId` in processing metadata
4. **Compliance**: Maintain audit trail of all messages

---

## 3️⃣ User Sessions Collection

### Purpose
Tracks user session activity, including conversations, messages, and agent launches within a session.

### Key Features
- ✅ Session activity tracking
- ✅ Analytics aggregation
- ✅ 180-day TTL for ended sessions

### Schema Structure

#### Required Fields

| Field | Type | Pattern/Values | Description |
|-------|------|---------------|-------------|
| `_id` | string | `session_[alphanumeric]` | Unique session ID |
| `userId` | string | `user_[alphanumeric]` | User identifier |
| `sessionId` | string | `sess_[alphanumeric]` | Session identifier |
| `createdAt` | date | - | Creation timestamp |

#### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `timeRange` | object | Session time range |
| `activity` | object | Session activity metrics |

#### Time Range Structure

| Field | Type | Description |
|-------|------|-------------|
| `startedAt` | date | Session start time |
| `endedAt` | date/null | Session end time |
| `durationSeconds` | int/null | Session duration in seconds |

#### Activity Structure

| Field | Type | Description |
|-------|------|-------------|
| `conversationIds` | array | List of conversation IDs in this session |
| `messageCount` | int | Total messages in session |
| `agentsLaunched` | array | List of agent IDs launched |
| `intents` | object | Count of each intent type |
| `totalTokensUsed` | int | Total tokens consumed in session |
| `timezone` | string | User timezone |

### Indexes

| Index Name | Fields | Purpose |
|------------|--------|---------|
| `idx_userId_startedAt` | `userId`, `timeRange.startedAt` (desc) | Get user's sessions ordered by start time |
| `idx_sessionId` | `sessionId` | Find session by ID (unique) |
| `idx_startedAt` | `timeRange.startedAt` (desc) | Global session listing |
| `idx_endedAt_ttl` | `timeRange.endedAt` | Auto-delete ended sessions after 180 days |

### Use Cases

1. **Session Analytics**: Track user engagement and session duration
2. **User Behavior**: Analyze conversation patterns and agent usage
3. **Performance Monitoring**: Track tokens used per session
4. **Retention Analysis**: Understand user session patterns

---

## 4️⃣ Wallet Transactions Collection

### Purpose
Records all wallet balance transactions including debits, credits, and refunds with strict validation.

### Key Features
- ✅ Strict validation (validationLevel: strict)
- ✅ Complete transaction audit trail
- ✅ Support for multiple transaction types
- ✅ Related entity tracking

### Schema Structure

#### Required Fields

| Field | Type | Pattern/Values | Description |
|-------|------|---------------|-------------|
| `_id` | string | `txn_[hex]` | Unique transaction ID |
| `userId` | string | `user_[alphanumeric]` | User identifier |
| `transactionType` | enum | `debit`, `credit`, `refund` | Transaction type |
| `amount` | double | - | Transaction amount (positive) |
| `balanceBefore` | double (min 0) | - | Balance before transaction |
| `balanceAfter` | double (min 0) | - | Balance after transaction |
| `status` | enum | `pending`, `completed`, `failed`, `reversed` | Transaction status |
| `timestamp` | date | - | Transaction timestamp |
| `createdAt` | date | - | Creation timestamp |

#### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `currency` | enum | `USD`, `INR` |
| `relatedTo` | object | Related entity information |
| `description` | string (max 500) | Transaction description |

#### Related To Structure

| Field | Type | Description |
|-------|------|-------------|
| `type` | enum | `agent_launch`, `message`, `recharge`, `refund` |
| `id` | string | Related entity ID |
| `agentId` | string/null | Agent ID if applicable |
| `conversationId` | string/null | Conversation ID if applicable |

### Indexes

| Index Name | Fields | Purpose |
|------------|--------|---------|
| `idx_userId_timestamp` | `userId`, `timestamp` (desc) | Get user's transactions ordered by time |
| `idx_userId_status_timestamp` | `userId`, `status`, `timestamp` (desc) | Filter by user and status |
| `idx_relatedType_timestamp` | `relatedTo.type`, `timestamp` (desc) | Find transactions by related type |
| `idx_relatedId` | `relatedTo.id` | Find transactions by related entity ID |
| `idx_status_createdAt` | `status`, `createdAt` (desc) | Find transactions by status |
| `idx_timestamp` | `timestamp` (desc) | Global transaction listing |

### Use Cases

1. **Transaction History**: Display user's wallet transaction history
2. **Audit Trail**: Complete record of all balance changes
3. **Analytics**: Analyze spending patterns and transaction types
4. **Reconciliation**: Match transactions with related entities (agents, conversations)

---

## 🔗 Collection Relationships

```
┌─────────────────┐
│   conversations │
│                 │
│  _id: conv_*    │◄─────┐
│  userId         │      │
│  recentMessages │      │
│  summary        │      │
└─────────────────┘      │
                         │
                         │ references
                         │
┌─────────────────┐      │
│    messages     │      │
│                 │      │
│  _id: msg_*     │      │
│  conversationId │──────┘
│  userId         │
│  role, content  │
└─────────────────┘
         │
         │ references
         │
┌─────────────────┐
│ wallet_transactions │
│                 │
│  _id: txn_*     │
│  userId         │
│  relatedTo: {   │
│    conversationId│
│    agentId      │
│  }              │
└─────────────────┘
```

---

## 📊 Data Flow

### Message Creation Flow

1. **User sends message** → API receives request
2. **Fetch conversation** → Get `conversations` document
3. **Retrieve context** → Get `recentMessages` (last 10) + `conversationSummary`
4. **Process with LLM** → Generate AI response
5. **Store messages** → Save to `messages` collection
6. **Update conversation** → Update `recentMessages` (FIFO), update stats
7. **Create transaction** → If agent launched, create `wallet_transactions` entry

### Context Window Management

```
Conversation Length < 20 messages:
  → Use all messages

Conversation Length >= 20 messages:
  → Use conversationSummary + recentMessages (last 10)
  → Saves ~70% tokens vs full history
```

---

## 🎯 Key Design Decisions

### 1. FIFO Queue for Recent Messages
- **Why**: Fast access to last 10 messages without querying `messages` collection
- **Benefit**: Reduced latency for LLM context retrieval
- **Trade-off**: Only last 10 messages in conversation document

### 2. Separate Messages Collection
- **Why**: Store complete message history without document size limits
- **Benefit**: Scalable, supports analytics and full history retrieval
- **Trade-off**: Requires additional query for full history

### 3. Conversation Summarization
- **Why**: Reduce LLM token costs for long conversations
- **Benefit**: Maintain context while using fewer tokens
- **Trade-off**: Requires summarization processing overhead

### 4. TTL Indexes
- **Why**: Automatic cleanup of old data
- **Benefit**: Reduced storage costs, compliance with data retention
- **Trade-off**: Data permanently deleted after TTL expires

---

## 📈 Performance Considerations

### Query Patterns

| Query Type | Collection | Index Used | Performance |
|------------|------------|------------|-------------|
| Get user conversations | `conversations` | `idx_userId_lastMessageAt` | ⚡ Fast |
| Get last 10 messages | `conversations` | Direct array access | ⚡⚡ Very Fast |
| Get full message history | `messages` | `idx_conversationId_timestamp` | ⚡ Fast |
| Get user transactions | `wallet_transactions` | `idx_userId_timestamp` | ⚡ Fast |
| Get session activity | `user_sessions` | `idx_userId_startedAt` | ⚡ Fast |

### Optimization Strategies

1. **Recent Messages**: Stored in conversation document for instant access
2. **Indexes**: All common query patterns are indexed
3. **TTL Indexes**: Automatic cleanup reduces storage and improves performance
4. **Sparse Indexes**: Only index documents with specific fields (e.g., errors, tags)

---

## 🔒 Data Validation

| Collection | Validation Level | Action on Violation |
|------------|------------------|---------------------|
| `conversations` | Moderate | Warn |
| `messages` | Moderate | Warn |
| `user_sessions` | Moderate | Warn |
| `wallet_transactions` | **Strict** | **Error** |

**Note**: Wallet transactions use strict validation due to financial data integrity requirements.

---

## 📝 Summary

This database schema design provides:

✅ **Scalable Architecture**: Separate collections for different data types  
✅ **Performance Optimization**: Indexes on all common query patterns  
✅ **Cost Efficiency**: Conversation summarization reduces LLM token costs  
✅ **Data Integrity**: Schema validation ensures data quality  
✅ **Automatic Cleanup**: TTL indexes manage data retention  
✅ **Complete Audit Trail**: Full transaction and message history  

---

**Document Prepared By**: Development Team  
**Last Updated**: December 2024  
**Next Review**: Q1 2025











