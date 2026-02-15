#!/bin/bash

# ============================================================================
# Unified Query System - Chat API - cURL Examples
# ============================================================================
# Base URL (adjust if your server runs on a different host/port)
BASE_URL="https://ai-dev.mysellercentral.com/nlp-agents"

# ============================================================================
# 1. Health Check
# ============================================================================
echo "=== Health Check ==="
curl -X GET "${BASE_URL}/health" \
  -H "Content-Type: application/json"

echo -e "\n\n"

# ============================================================================
# 2. Root Endpoint (API Info)
# ============================================================================
echo "=== Root Endpoint ==="
curl -X GET "${BASE_URL}/" \
  -H "Content-Type: application/json"

echo -e "\n\n"

# ============================================================================
# 3. Basic Chat Query
# ============================================================================
echo "=== Basic Chat Query ==="
curl -X POST "${BASE_URL}/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me top 10 selling products",
    "user_id": 48
  }'

echo -e "\n\n"

# ============================================================================
# 4. Chat with Custom Schema
# ============================================================================
echo "=== Chat with Custom Schema ==="
curl -X POST "${BASE_URL}/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are my total sales this month?",
    "user_id": 51,
    "schema_name": "amazon"
  }'

echo -e "\n\n"

# ============================================================================
# 5. Chat with Include SQL
# ============================================================================
echo "=== Chat with Include SQL ==="
curl -X POST "${BASE_URL}/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me inventory levels for all products",
    "user_id": 48,
    "include_sql": true
  }'

echo -e "\n\n"

# ============================================================================
# 6. Chat with Include Full Data
# ============================================================================
echo "=== Chat with Include Full Data ==="
curl -X POST "${BASE_URL}/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "List all orders from last week",
    "user_id": 51,
    "include_data": true
  }'

echo -e "\n\n"

# ============================================================================
# 7. Complete Request with All Options
# ============================================================================
echo "=== Complete Request with All Options ==="
curl -X POST "${BASE_URL}/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me sales trends by product category for Q1 2024",
    "user_id": 51,
    "schema_name": "amazon",
    "include_data": true,
    "include_sql": true
  }'

echo -e "\n\n"

# ============================================================================
# 8. Sales Analysis Query
# ============================================================================
echo "=== Sales Analysis Query ==="
curl -X POST "${BASE_URL}/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are my top selling products?",
    "user_id": 48
  }'

echo -e "\n\n"

# ============================================================================
# 9. Inventory Check with SQL
# ============================================================================
echo "=== Inventory Check with SQL ==="
curl -X POST "${BASE_URL}/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me low stock items",
    "user_id": 48,
    "include_sql": true
  }'

echo -e "\n\n"

# ============================================================================
# 10. Request Visualization
# ============================================================================
echo "=== Request Visualization ==="
curl -X POST "${BASE_URL}/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me a chart of sales by month",
    "user_id": 48
  }'

echo -e "\n\n"

# ============================================================================
# 11. Order Analysis with Full Data
# ============================================================================
echo "=== Order Analysis with Full Data ==="
curl -X POST "${BASE_URL}/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "List all orders from January 2024",
    "user_id": 51,
    "include_data": true
  }'

echo -e "\n\n"

# ============================================================================
# Pretty Print JSON Response Examples
# ============================================================================
echo "=== Pretty Print JSON Response (using jq) ==="
echo "# If you have jq installed, pipe responses through it:"
echo "# curl -X POST \"${BASE_URL}/api/chat\" \\"
echo "#   -H \"Content-Type: application/json\" \\"
echo "#   -d '{\"message\": \"Show me top 10 products\", \"user_id\": 48}' | jq '.'"

echo -e "\n"

echo "=== Pretty Print JSON Response (using Python) ==="
echo "# Or using Python:"
echo "# curl -X POST \"${BASE_URL}/api/chat\" \\"
echo "#   -H \"Content-Type: application/json\" \\"
echo "#   -d '{\"message\": \"Show me top 10 products\", \"user_id\": 48}' | python3 -m json.tool"

echo -e "\n\n"

# ============================================================================
# Example: Multiple Independent Queries
# ============================================================================
echo "=== Example: Multiple Independent Queries ==="
echo "# Note: Each query is processed independently - no conversation context"

# Query 1
echo "Query 1: Sales Analysis"
curl -s -X POST "${BASE_URL}/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are my total sales this month?",
    "user_id": 48
  }' | python3 -m json.tool | head -20

echo -e "\n"

# Query 2 (independent - no context from Query 1)
echo "Query 2: Inventory Check"
curl -s -X POST "${BASE_URL}/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me inventory levels",
    "user_id": 48,
    "include_sql": true
  }' | python3 -m json.tool | head -20

echo -e "\n\n"
