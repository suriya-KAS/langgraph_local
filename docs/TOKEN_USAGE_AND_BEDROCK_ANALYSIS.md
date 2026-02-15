# AWS Bedrock  Analysis  
**Last updated:** 06 February 2026.

---

## Part 1 — Token Usage (Input & Output)

This section describes **where** the system calls the AI model, **how many** tokens (input and output) are used, and **how** that usage is reflected in the API and storage.

### 1.1 Overview: Who Calls the AI?

The chatbot uses **one central function** in the backend to talk to the AI model: `invoke_gemini_with_tokens`. Every AI-generated text (classification, answers, summaries) goes through this function. The model used is configured via **GEMINI_MODEL_ID** (default: `gemini-2.0-flash`).


| Component                      | What it does                                                   | Calls AI?                                           | Input tokens | Output tokens | Visible in API response? |
| ------------------------------ | -------------------------------------------------------------- | --------------------------------------------------- | ------------ | ------------- | ------------------------ |
| **Orchestrator (user intent)** | Classifies the user message and enriches the query             | Yes (1 call per user message)                       | Yes          | Yes           | **No** (logged only)     |
| **Product Detail**             | Answers product/feature/pricing questions using Knowledge Base | Yes (1 call when this category handles the message) | Yes          | Yes           | **Yes**                  |
| **Memory layer**               | Summarizes conversation every 4 messages                       | Yes (1 call per summary)                            | Yes          | Yes           | **No** (background)      |
|                                |                                                                |                                                     |              |               |                          |


So for a **single user message** that is handled by **Product Detail**:

- **Orchestrator** uses one AI call (classification + enrichment). Those tokens are **not** added to the response; they are only logged.
- **Product Detail** uses one AI call (answer generation). Those tokens **are** returned in the API and stored in the database.

The **token counts you see in the API and in the database** for a message are therefore **only** the tokens from the **category** that handled the message (today, the only category that calls the AI is Product Detail). Orchestrator and memory-layer tokens are real usage but not included in that number.

---

### 1.2 Orchestrator (User Intent)

- **Role:** Decides which category should handle the user’s message (e.g. product_detail, analytics_reporting, insights_kb) and produces an “enriched” query (e.g. resolving “it” from context) and extracts ASINs if present.
- **Where:** `src/core/orchestrator/user_intent.py` → `find_user_intent()` → `invoke_gemini_with_tokens()` (from `src/core/backend`).
- **Input:** One prompt containing:
  - Instructions (categories, routing rules, enrichment rules),
  - User context (marketplaces, wallet, login location),
  - Last few conversation turns,
  - Current user message.
- **Output:** Short JSON: `category`, `enriched_query`, `asins`.
- **Limits:** `max_tokens=200`, `temperature=0.1`.
- **Token reporting:** The function returns `(response_text, input_tokens, output_tokens)`. These values are **logged** (e.g. “Classification tokens - Input: X, Output: Y”) but **not** merged into the final result that the API returns. So orchestrator token usage is **not** visible in the chat API response or in the stored message metadata.

**Summary:** One AI call per user message; input/output tokens are tracked and logged but **not** included in the per-message token counts in the API.

---

### 1.3 Product Detail

- **Role:** Answers questions about the product (features, pricing, agents, integrations) using the Knowledge Base (today: Bedrock Knowledge Base with optional local file fallback). It also detects “agent_suggestion” vs “general_query” and returns an optional `agentId`.
- **Where:** `src/categories/product_detail.py` → `process_query()` → `invoke_gemini_with_tokens()` (from `src/core/backend`).
- **Input:** System prompt (including Knowledge Base snippet, user payload, language, username) plus conversation history and the current (enriched) user message.
- **Output:** Full natural-language answer plus a small JSON block (intent, agentId). Response is cleaned before sending to the user.
- **Limits:** `max_tokens=1000`, `temperature=0.1`.
- **Token reporting:** Returns `input_tokens` and `output_tokens` in the category result. The API and the database use **these** values for the message’s token metadata (e.g. `metadata.inputTokens`, `metadata.outputTokens`, `metadata.tokensUsed`).

**Summary:** One AI call when the user’s message is handled by Product Detail; these are the **only** tokens that appear in the chat API response and in stored message metadata for that turn.

---

### 1.4 Memory Layer (Conversation Summarization)

- **Role:** Every 4 messages, the system summarizes the last 4 messages into a short summary so that long conversations can stay within context limits.
- **Where:** `src/core/memory_layer.py` → `summarize_messages()` → `invoke_gemini_with_tokens()` (from `src/core/backend`).
- **Input:** System prompt (e-commerce memory instructions) plus the concatenated conversation chunk (e.g. “User: … Assistant: …”).
- **Output:** A summary string (no JSON).
- **Limits:** `max_tokens=700`, `temperature=0.1`.
- **Token reporting:** The call returns `(summary, input_tokens, output_tokens)` but the caller discards the token counts. So summarization **consumes** tokens but they are **not** logged or stored anywhere in the current implementation.

**Summary:** One AI call per 4 messages for summarization; tokens are used but **not** reported or visible in the API.

---

### 1.5 Backend: Single Entry Point for the AI Model

- **Where:** `src/core/backend.py`.
- **Function:** `invoke_gemini_with_tokens(formatted_messages, system_prompt, max_tokens, temperature)`.
- **Behavior:** Builds the request for the Gemini API, sends it, and reads from the response:
  - **Input tokens:** from `usage_metadata.prompt_token_count`.
  - **Output tokens:** from `usage_metadata.candidates_token_count`.
- **Model:** From environment variable **GEMINI_MODEL_ID** (default `gemini-2.0-flash`). This is the single model used for:
  - Orchestrator (user intent),
  - Product Detail (answer generation),
  - Memory layer (summarization).

All token counts in this document refer to this single backend entry point and the same model.

---

### 1.6 How Tokens Flow to the API and Database

- **API response:** The chat API returns `metadata.inputTokens`, `metadata.outputTokens`, and `metadata.tokensUsed` (input + output). These values are taken **only** from the **category** result (e.g. Product Detail). So for Product Detail flows you see Product Detail tokens; for Analytics, Insights KB, etc. you see 0.
- **Database:** When an assistant message is saved, the same category-level token counts are stored (e.g. in `processing.inputTokens`, `processing.outputTokens`, `processing.tokensUsed`).
- **Total real usage per request:** For a message handled by Product Detail, **total** tokens = orchestrator call + product_detail call. For any message, if a summary was just created, add one more call (memory layer). Those extra calls are not reflected in the per-message token fields in the API or DB.

---

### 1.7 Quick Reference Table


| Call site                  | Purpose                         | Max output tokens | Tokens in API/DB? |
| -------------------------- | ------------------------------- | ----------------- | ----------------- |
| Orchestrator (user_intent) | Classify + enrich query + ASINs | 200               | No (logged only)  |
| Product Detail             | Answer with KB + intent/agentId | 1000              | Yes               |
| Memory layer               | Summarize last 4 messages       | 700               | No (not logged)   |
| Other categories           | No AI call                      | —                 | Yes (as 0)        |


---

## Part 2 — Replacing Current AI with AWS Bedrock: Pros and Cons

This section compares **keeping the current setup** (Gemini for all LLM calls, as in the code today) with **replacing it with AWS Bedrock** for those same calls (classification, product-detail answers, and conversation summarization). It is written so that product, engineering, and leadership can weigh trade-offs without needing deep implementation detail.

---

### 2.1 What “Replacing with Bedrock” Means

- **Today:** All LLM calls go to **Google Gemini** (e.g. `gemini-2.0-flash`) via `invoke_gemini_with_tokens`. Knowledge Base retrieval already uses **AWS Bedrock** (Bedrock Knowledge Base); only the “generate text” part uses Gemini.
- **After change:** The same three use cases (orchestrator, product_detail, memory summarization) would call **Bedrock’s inference APIs** (e.g. Claude or Mistral on Bedrock) instead of Gemini. Knowledge Base could stay on Bedrock; only the model behind `invoke_gemini_with_tokens` would be swapped to a Bedrock model.

The comparison below is **current Gemini vs. using a Bedrock model** for those LLM calls.

---

### 2.2 Pros of Moving to AWS Bedrock (for LLM)


| Area                                 | Benefit                                                                                                                                                |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Single cloud for AI**              | Both Knowledge Base (already Bedrock) and text generation would be on AWS. One vendor for quotas, billing, and support.                                |
| **Unified quotas and limits**        | You can reason about TPS, concurrency, and token limits in one place (Bedrock) instead of splitting between Google and AWS.                            |
| **Easier compliance and governance** | If your organization standardizes on AWS for data and AI, keeping all model traffic in the same account/region can simplify audits and data residency. |
| **Choice of models**                 | Bedrock offers multiple families (e.g. Claude, Mistral, Llama). You can switch or A/B test models without changing to a different cloud provider.      |
| **Pricing and commitment**           | You may already have AWS commitments; Bedrock usage can align with that. Reserved capacity or committed use can reduce effective cost.                 |
| **Operational familiarity**          | Teams already using Bedrock for Knowledge Base and (in some docs) for agents can reuse the same monitoring, IAM, and networking patterns.              |


---

### 2.3 Cons / Risks of Moving to AWS Bedrock (for LLM)


| Area                           | Risk or drawback                                                                                                                                                                                                                                                                                                                            |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Accuracy and behavior**      | Gemini and Bedrock models (e.g. Claude, Mistral) are different. Classification and answer quality may change. You’ll need to re-validate intent accuracy, enrichment quality, and product-detail answers (including JSON blocks and agentId).                                                                                               |
| **Prompt and API differences** | Bedrock’s request/response format and tooling differ from Gemini. Prompts may need tuning; structured output (e.g. JSON in product_detail and user_intent) may need small changes or wrappers.                                                                                                                                              |
| **Latency**                    | End-to-end latency can change (better or worse) depending on region, model, and Bedrock’s current load. You should measure p50/p95 for classification and for product-detail responses before and after.                                                                                                                                    |
| **Token counting**             | Bedrock returns usage in a different shape. You’ll need to map it to your existing `input_tokens` / `output_tokens` so the API and DB stay consistent.                                                                                                                                                                                      |
| **Throttling and concurrency** | Bedrock has per-model, per-account (and often per-region) limits: requests per second, concurrent requests, and sometimes tokens per minute. Under load, you can see 429 / ThrottlingException. Your existing doc “PM_AWS_Concurrency_Throttling.md” already covers this; the same considerations apply if Bedrock also does the LLM calls. |
| **Vendor lock-in**             | More of your AI stack would be on AWS. Migrating away later would mean changing both Knowledge Base and inference.                                                                                                                                                                                                                          |
| **Cost**                       | List prices and effective cost (e.g. after commitments) for Bedrock vs. Gemini can differ by model and volume. A per-request or monthly cost comparison is recommended.                                                                                                                                                                     |


---

### 2.4 Accuracy

- **Current (Gemini):** Intent classification, query enrichment, and product-detail answers are tuned for the current prompts and Gemini’s behavior. Any change of model can shift behavior.
- **With Bedrock:** You should re-run intent classification tests, check enriched queries (especially follow-ups and multi-marketplace cases), and verify product-detail answers and JSON (intent/agentId) parsing. Plan for prompt and possibly logic tweaks.
- **Recommendation:** Treat a Bedrock switch as a model change that requires QA and possibly a short parallel run (shadow or A/B) before full cutover.

---

### 2.5 Latency

- **Current:** Latency is driven by Gemini’s API and your network. Typically one classification call plus one category call (e.g. product_detail) per user message.
- **With Bedrock:** Latency will depend on region, chosen model, and Bedrock’s load. It can be similar, better, or worse. Concurrency limits can also increase queueing and thus perceived latency during peaks.
- **Recommendation:** Define target p95 latency for a “full turn” (classification + category). Measure before and after with the same test set and load pattern.

---

### 2.6 Concurrency and Limits

- **Current (Gemini):** Gemini has its own rate and quota limits. Your app does not currently implement client-side rate limiting or queuing; every valid message triggers at least one (often two) LLM calls.
- **With Bedrock:** All those calls would hit Bedrock’s limits. Default quotas (e.g. TPS, concurrent requests, TPM) may be tight for spikes. You may need to:
  - Request quota increases,
  - Add client-side pacing or queuing,
  - Or use a fallback (e.g. another model or a cached response) when throttled.

The existing “PM_AWS_Concurrency_Throttling” document applies fully once LLM calls move to Bedrock.

---

### 2.7 Cost and Billing

- **Current:** You pay for Gemini usage (input/output tokens) and separately for AWS (e.g. Bedrock Knowledge Base, infrastructure).
- **With Bedrock:** You would pay for Bedrock inference (tokens or requests, depending on model) plus existing Bedrock KB and other AWS services. Compare:
  - Token (or request) rates for your expected volume,
  - Any committed use or reserved capacity on either side.
- **Recommendation:** Estimate monthly token usage (orchestrator + product_detail + memory) and compare list and effective cost for Gemini vs. the chosen Bedrock model(s).

---

### 2.8 Operational and Reliability


| Topic          | Note                                                                                                                                                                                                                                                                                                             |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Monitoring** | Today you can monitor Gemini calls and token usage in logs. With Bedrock, you’d use CloudWatch and Bedrock metrics; ensure token counts and errors are still visible for the same flows.                                                                                                                         |
| **Errors**     | User-facing messages (e.g. “Failed to generate response from AI model”) today can be due to Gemini or network issues. With Bedrock, add ThrottlingException and Bedrock-specific errors to runbooks and, if desired, to slightly more specific user messaging (e.g. “Too many requests; try again in a moment”). |
| **Retries**    | Your backend already retries on certain failures. Bedrock retry behavior (e.g. 429 with optional Retry-After) should be aligned with that logic.                                                                                                                                                                 |
| **SLA**        | Check Bedrock’s SLA (availability, exclusions for throttling) and compare with your targets and with what you assume for Gemini.                                                                                                                                                                                 |


---

### 2.9 Summary Table: Gemini vs. Bedrock (for LLM)


| Dimension                | Current (Gemini)              | With Bedrock (LLM)                                 |
| ------------------------ | ----------------------------- | -------------------------------------------------- |
| **Vendor**               | Google (inference) + AWS (KB) | AWS only (KB + inference)                          |
| **Accuracy**             | Known for current prompts     | Re-validation and tuning needed                    |
| **Latency**              | Depends on Gemini/network     | Depends on region/model; measure                   |
| **Concurrency / limits** | Gemini quotas                 | Bedrock quotas; may need increases or pacing       |
| **Token reporting**      | Already integrated            | Must map Bedrock usage to existing fields          |
| **Cost**                 | Gemini pricing                | Bedrock pricing; compare at your volume            |
| **Ops**                  | Gemini + AWS                  | Single stack (Bedrock); update monitoring/runbooks |
| **Lock-in**              | Split (Google + AWS)          | More weight on AWS                                 |


---

## Appendix: Where to Find It in the Code


| What                         | File(s)                                                                                           |
| ---------------------------- | ------------------------------------------------------------------------------------------------- |
| Single LLM entry point       | `src/core/backend.py` — `invoke_gemini_with_tokens`                                               |
| Orchestrator (user intent)   | `src/core/orchestrator/user_intent.py` — `find_user_intent`                                       |
| Product Detail               | `src/categories/product_detail.py` — `process_query`                                              |
| Memory summarization         | `src/core/memory_layer.py` — `summarize_messages`                                                 |
| Token counts in API and DB   | `src/api/routes.py` (metadata), `database/schema/messages.py`, `database/conversation_storage.py` |
| Bedrock throttling / PM view | `docs/PM_AWS_Concurrency_Throttling.md`                                                           |


---

*This document is based on the codebase as of February 2026. If the backend adds or changes LLM call sites (e.g. more categories calling the model, or token aggregation from orchestrator/memory), this doc should be updated accordingly.*