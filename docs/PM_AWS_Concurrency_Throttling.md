# Product Manager POV: AWS Bedrock Concurrency & Throttling

**Audience:** Product, Support, and anyone escalating to AWS  
**Last updated:** Feb 2026  
**Context:** Chatbot uses **AWS Bedrock** (Mistral Large) for intent classification and response generation. Throttling and concurrency limits can cause user-facing failures.

---

## 1. What is the issue?

**In short:** When AWS Bedrock is under load or our usage hits its limits, the service returns **throttling** (HTTP 429) or **ThrottlingException**. After our app retries up to 3 times with exponential backoff, the request can still fail. The user then sees a generic error such as:

- **"Failed to generate response from AI model"** (with `MODEL_ERROR` in the API response)

So from a **product/customer perspective**:

- Chat messages sometimes fail with no clear explanation.
- Failures can correlate with peak usage (many users or many messages at once).
- There is no in-app distinction between “temporary overload” (retry later) vs “something is broken” (contact support).

**Technically**, the issue is:

- **Throttling (429 / ThrottlingException):** “Too many requests” — we exceeded the allowed request rate or concurrency for our account/model.
- **Concurrency limits:** Bedrock limits how many requests can be in flight at the same time per model/endpoint. Hitting that limit also leads to throttling-like behavior or errors.

So the “issue” is: **we are hitting AWS-enforced rate and concurrency limits**, and after retries we still fail and surface a generic model error to the user.

---

## 2. Why is it happening?

From the **codebase** and design:

| Factor | What the codebase does |
|--------|-------------------------|
| **Single model, single region** | All LLM calls use one model: `mistral.mistral-large-2402-v1:0` in one region (e.g. `us-east-1`). All traffic shares the same Bedrock quota. |
| **No client-side rate limiting** | The app does not limit how many Bedrock requests we send per second or per user. Every valid user message triggers at least one Bedrock call (intent + response); some flows may trigger more (e.g. KB + LLM). |
| **No request queuing** | When load spikes, we do not queue requests and send them at a steady rate. We send as fast as users send messages, so short bursts can exceed Bedrock’s allowed TPS/concurrency. |
| **Retry then fail** | We retry on 429/5xx/ThrottlingException up to **3 times** with exponential backoff (1s, 2s, 4s). If all retries fail (e.g. sustained throttling), we return `MODEL_ERROR` and the user sees “Failed to generate response from AI model”. |
| **Quota is account-level** | Bedrock quotas are typically per account (and per model/endpoint). So all our environments and users share the same quota unless we have separate accounts or reserved capacity. |

So **why it’s happening** in practice can be one or more of:

1. **Traffic spike** — More concurrent users or messages than our current Bedrock quota supports.
2. **Burst pattern** — Many requests in a short window (e.g. after a campaign or feature launch) hitting TPS/concurrency limits.
3. **Quota too low** — Default Bedrock quotas for Mistral in our region are not enough for our target traffic.
4. **Other workloads** — If the same AWS account uses Bedrock for other apps or tests, they share the same quota.

---

## 3. What we do today (for context when talking to AWS)

- **Retry logic:** We treat 429, 500, 502, 503, 504 and `ThrottlingException` / `ServiceUnavailable` / `InternalServerError` as retryable and retry up to 3 times with exponential backoff.
- **Error to user:** After retries, we return a generic model error; we do **not** currently return a specific “rate limit exceeded” or “please try again in a few seconds” message.
- **Model:** `mistral.mistral-large-2402-v1:0` via Bedrock in the configured region (e.g. `us-east-1`).

---

## 4. Questions to ask when escalating to AWS

Use these when opening a case or talking to AWS about Bedrock throttling and concurrency so you get actionable answers.

### 4.1 Quotas and limits

1. **What are our current quotas for this model and region?**  
   - Requests per second (TPS)?  
   - Concurrent requests (in-flight)?  
   - Tokens per minute (TPM) if applicable?

2. **Are quotas per account, per region, or per model?**  
   - How is our Mistral usage (e.g. `mistral.mistral-large-2402-v1:0`) counted against these?

3. **Where can we see our usage and throttling in the console or via API?**  
   - CloudWatch metrics, Service Quotas console, or other tools?

### 4.2 Throttling behavior and errors

4. **When we get HTTP 429 or ThrottlingException, is that purely rate/concurrency limit, or can it also indicate a temporary service issue?**  
   - How should we distinguish “we exceeded quota” from “AWS side issue”?

5. **Does Bedrock return a Retry-After header or a recommended backoff in the error payload?**  
   - If yes, what’s the exact field/header so we can use it for retries and user messaging?

6. **What is the recommended retry strategy for 429/ThrottlingException?**  
   - Exponential backoff only, or does AWS recommend something else (e.g. token bucket, jitter)?

### 4.3 Concurrency and scaling

7. **How does “concurrent requests” work for our model?**  
   - Is it “number of requests being processed at the same time,” and is there a hard cap we’re hitting?

8. **How can we request a quota increase (TPS and/or concurrency)?**  
   - Process (e.g. Service Quotas console, support case), typical timeline, and whether we need a business justification.

9. **Do you offer reserved capacity or committed usage for Bedrock (e.g. guaranteed TPS/concurrency)?**  
   - If yes, how do we sign up and what are the minimums and pricing?

### 4.4 Reliability and SLA

10. **What is the SLA for Bedrock (e.g. availability %, exclusions for throttling)?**  
    - Does throttling (429) count as “service available” or as an SLA exclusion?

11. **Is there a status page or recommended way to check for known throttling or capacity issues in our region?**

### 4.5 Product and UX

12. **What user-facing message does AWS recommend when a request fails due to throttling?**  
    - e.g. “Too many requests; please try again in a few seconds.”

13. **Are there best practices for reducing throttling (e.g. batching, request pacing, or using multiple models/regions)?**

---

## 5. Summary for internal comms

- **Issue:** Users see “Failed to generate response from AI model” when Bedrock throttles (429) or hits concurrency limits and our retries don’t succeed.
- **Cause:** We share a single Bedrock model/region, have no client-side rate limiting or queuing, and likely hit account/model-level TPS or concurrency limits during peaks.
- **Escalation:** Use the questions in **Section 4** with AWS to get exact quotas, recommended retry/backoff, quota increase process, and guidance on user-facing messaging and scaling.

---

*Source: Derived from codebase (e.g. `src/core/backend.py` retry logic, `src/api/routes.py` error handling, `src/core/models.py` error codes, and `COMPREHENSIVE_DOCUMENTATION.md`).*
