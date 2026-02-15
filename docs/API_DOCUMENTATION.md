# MySellerCentral Chatbot API

**Base URL:** `http://localhost:8502`

---

## Endpoints

### 1. Health Check
```
GET /health
```
**Response:**
```json
{ "status": "healthy" }
```

---

### 2. Chat
```
POST /api/chat
```

**Request Body:**
```json
{
  "message": "string",              // Required
  "language": "English",            // Optional (default: "English")
  "chat_history": [                 // Optional
    {
      "role": "user" | "assistant",
      "content": "string"
    }
  ]
}
```

**Response:**
```json
{
  "response": "string",  // May contain Markdown
  "status": "success"
}
```

**Example:**
```javascript
const response = await fetch('http://localhost:8502/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: 'What AI agents are available?',
    language: 'English',
    chat_history: []
  })
});
const data = await response.json();
```

---

## Supported Languages
- English (default)
- Spanish
- Hindi
- French
- German

---

## Error Responses

**422 Validation Error:**
```json
{ "detail": "field required" }
```

**500 Server Error:**
```json
{ "detail": "Error processing chat request: ..." }
```

---

## Notes
- Responses contain Markdown - render with a Markdown library
- Include `chat_history` for conversation context
- Keep `chat_history` to last 10-20 messages

