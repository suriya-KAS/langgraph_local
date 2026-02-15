# Quick Reference - cURL Commands for Postman Testing

Base URL: `https://ai-dev.mysellercentral.com/nlp-agents`

---

## 🚀 Most Common Requests

### 1. Basic Chat Query
```bash
curl -X POST "https://ai-dev.mysellercentral.com/nlp-agents/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me top 10 selling products",
    "user_id": 48
  }'
```

### 2. Include SQL in Response
```bash
curl -X POST "https://ai-dev.mysellercentral.com/nlp-agents/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me inventory levels",
    "user_id": 48,
    "include_sql": true
  }'
```

### 3. Include Full Data Results
```bash
curl -X POST "https://ai-dev.mysellercentral.com/nlp-agents/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "List all orders from last week",
    "user_id": 51,
    "include_data": true
  }'
```

### 4. Complete Request with All Options
```bash
curl -X POST "https://ai-dev.mysellercentral.com/nlp-agents/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me sales trends by product category for Q1 2024",
    "user_id": 51,
    "schema_name": "amazon",
    "include_data": true,
    "include_sql": true
  }'
```

### 5. Health Check
```bash
curl -X GET "https://ai-dev.mysellercentral.com/nlp-agents/health" \
  -H "Content-Type: application/json"
```

### 6. Root Endpoint
```bash
curl -X GET "https://ai-dev.mysellercentral.com/nlp-agents/" \
  -H "Content-Type: application/json"
```

---

## 📋 Postman Setup

1. **Import Collection**: Import `Postman_Collection.json` into Postman
2. **Test Endpoints**: All requests are pre-configured and ready to use
3. **Each query is independent** - no conversation context is maintained

---

## 🔑 Required Fields
- `message` (string): Your question
- `user_id` (integer): Client ID (minimum: 1)

## ⚙️ Optional Fields
- `schema_name` (string): Database schema (default: "amazon")
- `include_data` (boolean): Include full results (default: false)
- `include_sql` (boolean): Include SQL query (default: false)

---

## 📝 Response Structure

```json
{
  "success": true,
  "message": "AI's response message",
  "timestamp": "2024-01-01T12:00:00",
  "query_executed": true,
  "row_count": 10,
  "data_preview": [...],
  "generated_sql": "SELECT ...",
  "domains": ["business", "inventory"],
  "selected_tables": ["products", "orders"],
  "visualization": {...}
}
```

---

## 💡 Notes

- **No conversation history**: Each request is processed independently
- **Fresh queries only**: No context from previous requests
- **Visualization support**: Check `visualization` field in responses for charts
- **Data preview**: Only first 10 rows shown unless `include_data: true`
