# Currency-Based Pricing Testing cURL Examples

Test the location-based currency feature (INR for India, USD for others).

**Base URL:** `http://localhost:8502`

**Note:** Currency detection priority:
1. `loginLocation` (primary) - "India" → INR, others → USD
2. `country` (fallback) - "IN"/"IND"/"INDIA" → INR, others → USD
3. `timezone` (fallback) - India timezones → INR, others → USD

---

## Test 1: India User with loginLocation (Should show ₹ INR prices)

```bash
curl -X POST http://localhost:8502/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I need to list my products",
    "conversationId": "conv_test_india_001",
    "context": {
      "userId": "user_india_001",
      "loginLocation": "India",
      "clientInfo": {
        "device": "mobile",
        "appVersion": "1.0.0",
        "timezone": "Asia/Kolkata",
        "platform": "android",
        "country": "IN"
      }
    },
    "language": "English"
  }'
```

**Expected Response:**
- Currency: `"INR"` (detected from loginLocation: "India")
- Currency Symbol: `"₹"`
- Agent costs should show in INR (e.g., `cost: 30` for Smart Listing Agent)

---

## Test 2: US User with loginLocation (Should show $ USD prices)

```bash
curl -X POST http://localhost:8502/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What AI agents are available?",
    "conversationId": "conv_test_us_002",
    "context": {
      "userId": "user_us_002",
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

**Expected Response:**
- Currency: `"USD"` (detected from loginLocation: "US")
- Currency Symbol: `"$"`
- Prices in $

---

## Test 3: India User (Fallback: Country-based detection)

```bash
curl -X POST http://localhost:8502/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I want to create better product listings",
    "conversationId": "conv_test_india_003",
    "context": {
      "userId": "user_india_003",
      "clientInfo": {
        "device": "desktop",
        "appVersion": "1.0.0",
        "timezone": "Asia/Kolkata",
        "platform": "web",
        "country": "IN"
      }
    },
    "language": "English"
  }'
```

**Expected Response:**
- Currency: `"INR"` (detected from country: "IN" - fallback when loginLocation not provided)
- Currency Symbol: `"₹"`
- Agent costs should show in INR (e.g., `cost: 30` for Smart Listing Agent)

---

## Test 4: Other Location (Should show $ USD prices)

```bash
curl -X POST http://localhost:8502/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me all available agents",
    "conversationId": "conv_test_other_001",
    "context": {
      "userId": "user_other_001",
      "loginLocation": "Other",
      "clientInfo": {
        "device": "mobile",
        "appVersion": "1.0.0",
        "timezone": "Europe/London",
        "platform": "ios",
        "country": "GB"
      }
    },
    "language": "English"
  }'
```

**Expected Response:**
- Currency: `"USD"` (detected from loginLocation: "Other" - non-India)
- Currency Symbol: `"$"`
- Prices in $

---

## Test 5: Fallback - Timezone-based detection (no loginLocation or country)

```bash
curl -X POST http://localhost:8502/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I need help with A+ content",
    "conversationId": "conv_test_ca_001",
    "context": {
      "userId": "user_ca_001",
      "clientInfo": {
        "device": "tablet",
        "appVersion": "1.0.0",
        "timezone": "America/Toronto",
        "platform": "ios"
      }
    },
    "language": "English"
  }'
```

**Expected Response:**
- Currency: `"USD"` (detected from timezone - not India timezone, fallback when loginLocation/country not provided)
- Prices in $

---

## Expected Agent Prices

Based on `agents_cache.json`:

### INR Prices (India):
- Smart Listing Agent: ₹30
- Text Grading: ₹20
- Image Grading: ₹25
- Banner Generator: ₹20
- Lifestyle Generator: ₹20
- Infographic Generator: ₹20
- A+ Content: ₹50
- A+ Video: ₹50
- Competition Alerts: ₹10
- Color Variants: ₹10

### USD Prices (International):
- Smart Listing Agent: $0.50
- Text Grading: $0.25
- Image Grading: $0.35
- Banner Generator: $0.25
- Lifestyle Generator: $0.25
- Infographic Generator: $0.25
- A+ Content: $1.00
- A+ Video: $1.00
- Competition Alerts: $0.15
- Color Variants: $0.15

---

## Response Structure Example

### India User Response:
```json
{
  "success": true,
  "data": {
    "messageId": "msg_abc123",
    "reply": "...",
    "components": {
      "agentCard": {
        "agentId": "smart-listing",
        "name": "Smart Listing Agent",
        "icon": "📝",
        "cost": 30,
        "currency": "INR",
        "currencySymbol": "₹",
        "walletAfter": 70,
        "features": [...],
        "marketplace": ["Amazon", "ONDC", "eBay"]
      }
    },
    "walletBalance": 100.0
  }
}
```

### US User Response:
```json
{
  "success": true,
  "data": {
    "messageId": "msg_xyz789",
    "reply": "...",
    "components": {
      "agentCard": {
        "agentId": "smart-listing",
        "name": "Smart Listing Agent",
        "icon": "📝",
        "cost": 0.50,
        "currency": "USD",
        "currencySymbol": "$",
        "walletAfter": 99.50,
        "features": [...],
        "marketplace": ["Amazon", "ONDC", "eBay"]
      }
    },
    "walletBalance": 100.0
  }
}
```

---

## Quick Test Script

Save as `test_currency.sh`:

```bash
#!/bin/bash

echo "Testing India User (INR) with loginLocation..."
curl -X POST http://localhost:8502/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What agents are available?",
    "conversationId": "test_india",
    "context": {
      "userId": "test_india",
      "loginLocation": "India",
      "clientInfo": {
        "device": "desktop",
        "appVersion": "1.0.0",
        "timezone": "Asia/Kolkata",
        "country": "IN"
      }
    }
  }' | jq '.data.components.agentCard | {cost, currency, currencySymbol}'

echo -e "\n\nTesting US User (USD) with loginLocation..."
curl -X POST http://localhost:8502/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What agents are available?",
    "conversationId": "test_us",
    "context": {
      "userId": "test_us",
      "loginLocation": "US",
      "clientInfo": {
        "device": "desktop",
        "appVersion": "1.0.0",
        "timezone": "America/New_York",
        "country": "US"
      }
    }
  }' | jq '.data.components.agentCard | {cost, currency, currencySymbol}'
```

Make it executable:
```bash
chmod +x test_currency.sh
./test_currency.sh
```

---

## Verification Checklist

- [ ] India user with loginLocation="India" shows ₹ prices
- [ ] US/Other user with loginLocation="US"/"Other" shows $ prices
- [ ] Fallback: Country-based detection works (when loginLocation not provided)
- [ ] Fallback: Timezone-based detection works (when loginLocation and country not provided)
- [ ] Currency field is present in AgentCard
- [ ] CurrencySymbol field is present in AgentCard
- [ ] Costs match expected values from cache
- [ ] loginLocation takes priority over country/timezone

---

## Troubleshooting

**Issue: Currency not detected correctly**
- Check logs for: `"Detected currency: ..."`
- Verify `loginLocation` (primary), `country` (fallback), or `timezone` (fallback) is in request
- Priority: loginLocation > country > timezone
- Default is USD if none provided

**Issue: Wrong prices shown**
- Verify `agents_cache.json` has correct INR/USD values
- Check cache is loaded: Look for "Successfully loaded X agents from cache file"
- Clear cache if needed: Delete `.agents_cache.json` and restart server

**Issue: Currency field missing**
- Ensure you're using the updated API endpoint
- Check response includes `components.agentCard.currency`


