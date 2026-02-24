import os
import asyncio
import json
import re
from typing import Dict, Optional
from dotenv import load_dotenv
import sys
# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from utils.logger_config import get_logger

# Initialize logger
logger = get_logger(__name__)

load_dotenv()

# LLM model ID (Gemini) - used for logging and API response metadata
modelID = os.getenv("GEMINI_MODEL_ID", "gemini-2.0-flash")
logger.info(f"Using LLM model: {modelID} (Gemini)")

def format_docs(docs):
    """Format retrieved documents into a string."""
    logger.debug(f"Formatting {len(docs)} documents")
    formatted = "\n\n".join(doc.page_content for doc in docs)
    logger.debug(f"Formatted documents length: {len(formatted)} characters")
    return formatted

def parse_structured_response(response: str) -> Optional[Dict]:
    """
    Robust JSON extraction from LLM response.
    Handles markdown code blocks, trailing text, and malformed JSON.
    
    Args:
        response: Full LLM response text
        
    Returns:
        Dict with 'intent' and 'agentId' if found, None otherwise
    """
    logger.debug("Parsing structured response from LLM")
    # Strategy 1: Look for JSON in markdown code blocks
    json_patterns = [
        r'```json\s*(\{.*?\})\s*```',  # ```json {...} ```
        r'```\s*(\{.*?\})\s*```',      # ``` {...} ```
        r'`(\{.*?\})`',                 # `{...}`
    ]
    
    for i, pattern in enumerate(json_patterns):
        match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
        if match:
            try:
                parsed = json.loads(match.group(1))
                if 'intent' in parsed:
                    logger.info(f"Successfully parsed structured response using pattern {i+1}")
                    return parsed
            except (json.JSONDecodeError, IndexError) as e:
                logger.debug(f"Pattern {i+1} failed to parse JSON: {e}")
                continue
    
    # Strategy 2: Find JSON object at the end of response
    json_match = re.search(r'(\{[^{}]*"intent"[^{}]*\})', response, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(1))
            if 'intent' in parsed:
                logger.info("Successfully parsed structured response using strategy 2")
                return parsed
        except json.JSONDecodeError as e:
            logger.debug(f"Strategy 2 failed to parse JSON: {e}")
    
    # Strategy 3: Look for any JSON object with intent field
    json_match = re.search(r'\{[^{}]*"intent"[^{}]*\}', response, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(0))
            if 'intent' in parsed:
                logger.info("Successfully parsed structured response using strategy 3")
                return parsed
        except json.JSONDecodeError as e:
            logger.debug(f"Strategy 3 failed to parse JSON: {e}")
    
    logger.warning("Could not parse structured response from LLM output")
    return None

def clean_response_text(response: str, structured: Optional[Dict]) -> str:
    """
    Remove JSON block from response text for user-facing display.
    
    Args:
        response: Full LLM response text
        structured: Parsed structured data (if available)
        
    Returns:
        Cleaned response text without JSON blocks
    """
    if not structured:
        logger.debug("No structured data provided, returning response as-is")
        return response
    
    logger.debug("Cleaning response text by removing JSON blocks")
    # Remove JSON blocks from response
    patterns_to_remove = [
        r'```json\s*\{.*?\}\s*```',
        r'```\s*\{.*?\}\s*```',
        r'\{[^{}]*"intent"[^{}]*\}',
    ]
    
    clean_reply = response
    original_length = len(clean_reply)
    for pattern in patterns_to_remove:
        clean_reply = re.sub(pattern, '', clean_reply, flags=re.DOTALL | re.IGNORECASE)
    
    cleaned_length = len(clean_reply.strip())
    logger.debug(f"Cleaned response - original: {original_length} chars, cleaned: {cleaned_length} chars")
    return clean_reply.strip()

def format_messages_for_llm(chat_messages: list, system_prompt: str, freeform_text: str) -> tuple:
    """
    Format chat messages for LLM API (Gemini).

    Accepts plain dicts (``{"role": "…", "content": "…"}``) — no LangChain
    message types required.

    Args:
        chat_messages: List of message dicts with ``role`` and ``content`` keys.
        system_prompt: System prompt text.
        freeform_text: Current user message to append.

    Returns:
        Tuple of (formatted_messages_list, system_prompt_text)
    """
    formatted_messages = []
    for msg in chat_messages:
        if isinstance(msg, dict):
            role = msg.get("role", "")
            content = msg.get("content", "")
        else:
            # Backward compat: LangChain message objects (if any remain)
            role = getattr(msg, "type", "")
            if role == "human":
                role = "user"
            elif role == "ai":
                role = "assistant"
            content = getattr(msg, "content", "")
        if role in ("user", "assistant") and content:
            formatted_messages.append({"role": role, "content": content})
    formatted_messages.append({"role": "user", "content": freeform_text})
    return formatted_messages, system_prompt


# Gemini LLM (primary)
GEMINI_MODEL_ID = os.getenv("GEMINI_MODEL_ID", "gemini-2.0-flash")
_genai_client = None


def _get_genai_client():
    """Lazy-initialize Gemini client (uses GEMINI_API_KEY or GOOGLE_API_KEY from env)."""
    global _genai_client
    if _genai_client is None:
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Gemini requires GOOGLE_API_KEY or GEMINI_API_KEY in environment")
        from google import genai
        _genai_client = genai.Client(api_key=api_key)
        logger.info("Gemini client initialized")
    return _genai_client


def invoke_gemini_with_tokens(
    formatted_messages: list,
    system_prompt: str,
    max_tokens: int = 1000,
    temperature: float = 0.1,
) -> tuple:
    """
    Invoke Gemini model for all LLM calls (classification, generation, summarization).
    Returns (response_text, input_tokens, output_tokens).

    Args:
        formatted_messages: List of {"role": "user"|"assistant"|"system", "content": str}
        system_prompt: System instruction (can be empty)
        max_tokens: Max tokens to generate
        temperature: Sampling temperature

    Returns:
        Tuple of (response_text, input_tokens, output_tokens)
    """
    from google.genai import types
    client = _get_genai_client()
    parts = []
    for msg in formatted_messages:
        role = (msg.get("role") or "user").lower()
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        if role == "system":
            system_prompt = f"{system_prompt}\n{content}".strip() if system_prompt else content
        else:
            parts.append(content)
    user_content = "\n\n".join(parts) if parts else ""
    if not user_content:
        raise ValueError("No user content in formatted_messages for Gemini")
    config = types.GenerateContentConfig(
        system_instruction=system_prompt or None,
        max_output_tokens=max_tokens,
        temperature=temperature,
    )
    response = client.models.generate_content(
        model=GEMINI_MODEL_ID,
        contents=user_content,
        config=config,
    )
    response_text = (response.text or "").strip()
    if not response_text:
        raise ValueError("Empty response text from Gemini API")
    usage = getattr(response, "usage_metadata", None)
    input_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
    output_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0
    return response_text, input_tokens, output_tokens


async def my_chatbot_async(language, freeform_text, chat_history=None, username=None, user_id=None, context=None, return_flow=False):
    """
    Async version of chatbot function for concurrent request handling.
    Uses the **LangGraph workflow** to classify intent, route to the
    appropriate engine, and optionally generate product suggestions
    (agent-to-agent communication for analytics queries).
    
    Args:
        language: Response language
        freeform_text: User's message
        chat_history: Previous conversation messages
        username: User's name
        user_id: User ID for analytics queries (optional)
        context: Additional context dict (optional, will be merged with base context)
    
    Returns:
        Dict with keys: 'reply' (str), 'intent' (str), 'agentId' (str|None), 'category' (str).
        If return_flow=True, also includes 'langgraph_flow' with node-by-node flow summary.
    """
    try:
        logger.info(f"Processing async chatbot request - language: {language}, message length: {len(freeform_text)}")
        
        # Import LangGraph workflow (lazy import to avoid circular dependencies)
        from src.graph import get_workflow
        
        # Get compiled workflow
        workflow = get_workflow()
        
        # Prepare base context
        base_context = {
            "language": language,
            "username": username
        }
        
        # Add user_id to context if provided
        if user_id is not None:
            base_context["user_id"] = user_id
            logger.debug(f"Added user_id to context: {user_id}")
        
        # Merge with additional context if provided
        if context and isinstance(context, dict):
            base_context.update(context)
            logger.debug(f"Merged additional context: {list(context.keys())}")
        
        # Build initial state for the LangGraph workflow
        initial_state = {
            "user_message": freeform_text,
            "chat_history": chat_history or [],
            "context": base_context,
        }
        
        # Run workflow with flow tracing (logs node order, input/output per node)
        from src.graph.flow_tracer import run_workflow_with_flow, get_flow_summary
        result_state, flow = await run_workflow_with_flow(
            workflow, initial_state, log_flow=True, include_snapshots_in_flow=True
        )
        
        # Extract final result assembled by build_response_node
        final_result = result_state.get("final_result", {})
        
        logger.info(
            f"LangGraph workflow returned - category: {final_result.get('category')}, "
            f"intent: {final_result.get('intent')}, agentId: {final_result.get('agentId')}"
        )
        if return_flow:
            final_result = dict(final_result)
            final_result["langgraph_flow"] = get_flow_summary(flow)
        return final_result
        
    except Exception as e:
        error_msg = f"Error in chatbot: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise Exception(f"I encountered an error while processing your request. Please check that your Knowledge Base ID is correct and that the model has access. Error details: {str(e)}")

def my_chatbot(language, freeform_text, chat_history=None, username=None, user_id=None):
    """
    Synchronous wrapper for backward compatibility (used by Streamlit).
    Uses the **LangGraph workflow** under the hood.
    
    Args:
        language: Response language
        freeform_text: User's message
        chat_history: Previous conversation messages
        username: User's name
        user_id: User ID for analytics queries (optional)
    
    Returns:
        If structured output is available: Dict with 'reply', 'intent', 'agentId', 'category'
        Otherwise: str (backward compatible)
    """
    try:
        logger.info(f"Processing synchronous chatbot request - language: {language}, message length: {len(freeform_text)}")
        
        # Import LangGraph workflow (lazy import to avoid circular dependencies)
        from src.graph import get_workflow
        
        # Get compiled workflow
        workflow = get_workflow()
        
        # Prepare context
        context = {
            "language": language,
            "username": username
        }
        
        # Add user_id to context if provided
        if user_id is not None:
            context["user_id"] = user_id
            logger.debug(f"Added user_id to context: {user_id}")
        
        # Build initial state
        initial_state = {
            "user_message": freeform_text,
            "chat_history": chat_history or [],
            "context": context,
        }
        
        # Run async workflow in event loop with flow tracing (sync wrapper)
        import asyncio
        from src.graph.flow_tracer import run_workflow_with_flow
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        
        result_state, _flow = loop.run_until_complete(
            run_workflow_with_flow(workflow, initial_state, log_flow=True, include_snapshots_in_flow=True)
        )
        final_result = result_state.get("final_result", {})
        
        logger.info(f"LangGraph workflow returned - category: {final_result.get('category')}, intent: {final_result.get('intent')}, agentId: {final_result.get('agentId')}")
        return final_result
        
    except Exception as e:
        error_msg = f"Error in chatbot: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return f"I encountered an error while processing your request. Please check that your Knowledge Base ID is correct and that the model has access. Error details: {str(e)}"