# cURL Examples for Chat API

Quick reference guide for testing the Unified Query System Chat API endpoints.

## Base URL
```bash
BASE_URL="https://ai-dev.mysellercentral.com/nlp-agents"
```

---

## Postman Collection

A ready-to-use Postman collection is available in `Postman_Collection.json`.

### Import into Postman:
1. Open Postman
2. Click **Import** button (top left)
3. Select **File** tab
4. Choose `Postman_Collection.json` from this directory
5. All endpoints will be imported with pre-configured requests

The collection includes:
- All API endpoints pre-configured
- Example request bodies
- Ready-to-use requests for testing

---

## 1. Health Check
```bash
curl -X GET "https://ai-dev.mysellercentral.com/nlp-agents/health" \
  -H "Content-Type: application/json"
```

---

## 2. Root Endpoint
```bash
curl -X GET "https://ai-dev.mysellercentral.com/nlp-agents/" \
  -H "Content-Type: application/json"
```

---

## 3. Basic Chat Query
```bash
curl -X POST "https://ai-dev.mysellercentral.com/nlp-agents/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me top 10 selling products",
    "user_id": 48
  }'
```

---

## 4. Chat with Custom Schema
```bash
curl -X POST "https://ai-dev.mysellercentral.com/nlp-agents/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are my total sales this month?",
    "user_id": 51,
    "schema_name": "amazon"
  }'
```

---

## 5. Include Generated SQL in Response
```bash
curl -X POST "https://ai-dev.mysellercentral.com/nlp-agents/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me inventory levels for all products",
    "user_id": 48,
    "include_sql": true
  }'
```

---

## 6. Include Full Query Results
```bash
curl -X POST "https://ai-dev.mysellercentral.com/nlp-agents/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "List all orders from last week",
    "user_id": 51,
    "include_data": true
  }'
```

---

## 7. Complete Request with All Options
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

---

## 8. Pretty Print JSON Response (using jq)
```bash
curl -X POST "https://ai-dev.mysellercentral.com/nlp-agents/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me top 10 products",
    "user_id": 48
  }' | jq '.'
```

---

## 9. Pretty Print JSON Response (using Python)
```bash
curl -X POST "https://ai-dev.mysellercentral.com/nlp-agents/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me top 10 products",
    "user_id": 48
  }' | python3 -m json.tool
```

---

## Request Parameters

### Required Fields
- `message` (string): User's question or message
- `user_id` (integer): Client ID for data isolation (minimum: 1)

### Optional Fields
- `schema_name` (string): Database schema name (default: "amazon")
- `include_data` (boolean): Include full query results in response (default: false)
- `include_sql` (boolean): Include generated SQL in response (default: false)

---

## Response Structure

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
  "visualization": {...},
  "requires_clarification": false
}
```

---

## Example Queries

### Query 1: Sales Analysis
```bash
curl -X POST "https://ai-dev.mysellercentral.com/nlp-agents/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are my top selling products?",
    "user_id": 48
  }'
```

### Query 2: Inventory Check
```bash
curl -X POST "https://ai-dev.mysellercentral.com/nlp-agents/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me low stock items",
    "user_id": 48,
    "include_sql": true
  }'
```

### Query 3: Order Analysis with Full Data
```bash
curl -X POST "https://ai-dev.mysellercentral.com/nlp-agents/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "List all orders from January 2024",
    "user_id": 51,
    "include_data": true
  }'
```

### Query 4: Request Visualization
```bash
curl -X POST "https://ai-dev.mysellercentral.com/nlp-agents/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me a chart of sales by month",
    "user_id": 48
  }'
```

---

## Testing Tips

1. **Each query is independent** - no conversation context is maintained
2. **Set `include_sql: true`** to debug SQL generation issues
3. **Set `include_data: true`** to see full query results (otherwise only first 10 rows shown)
4. **Use `jq` or `python3 -m json.tool`** to format JSON responses for readability
5. **Check the `visualization` field** in responses for chart data when available
