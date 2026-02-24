import json
import os
import re
from typing import Tuple

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from utils.logger_config import get_logger

load_dotenv()  # loads DATABASE_URL_PRODUCTION from .env

logger = get_logger(__name__)
engine = create_engine(os.environ["DATABASE_URL"])
DEFAULT_SCHEMA = os.environ.get("AMAZON_SCHEMA", "amazon")
ORDER_TABLE = os.environ.get("AMAZON_ORDER_TABLE", "order")


def fetch_amazon_revenue_data(payload: dict, schema: str | None = None) -> dict:
    """
    Execute both Amazon revenue SQL queries and return their results.

    Args:
        payload: A dict that must contain "userId", used as client_id for both queries.
                 Example: {"userId": 48, ...}
        schema: Schema name (default: env AMAZON_SCHEMA or "amazon"). Used as table prefix
                (e.g. amazon.order, amazon.order_item).

    Returns:
        A dict with keys:
        - "amazon_revenue": list of sales_channel/revenue rows
        - "amazon_asin_wise_revenue": list of asin/category_id/category_name/asin_revenue rows

    Raises:
        ValueError: If payload does not contain "userId".
    """
    user_id = payload.get("userId")
    if user_id is None:
        logger.warning("fetch_amazon_revenue_data: payload missing userId")
        raise ValueError('payload must contain "userId"')
    client_id = int(user_id)
    sch = schema if schema is not None else DEFAULT_SCHEMA
    ord_tbl = ORDER_TABLE
    logger.info("fetch_amazon_revenue_data: starting for client_id=%s, schema=%s", client_id, sch)

    amazon_revenue_query = """
SELECT
o.sales_channel,
SUM(oi.item_price) AS revenue
FROM {schema}."{order_table}" o
JOIN {schema}."order_item" oi ON o.order_id = oi.order_id AND oi.item_status != 'CANCELED'
WHERE o.client_id = {client_id}
AND o.order_date >= CURRENT_DATE - INTERVAL '1 day'
AND o.order_date < CURRENT_DATE
AND o.order_status != 'CANCELED'
AND o.sales_channel NOT IN ('Non-Amazon', 'Non-Amazon IN')
GROUP BY o.sales_channel;
""".format(schema=sch, order_table=ord_tbl, client_id=client_id)

    amazon_asin_wise_revenue_query = """
SELECT
    pa.asin,
    pd.categories ->> 'ProductCategoryId'   AS category_id,
    pd.categories ->> 'ProductCategoryName' AS category_name,
    SUM(oi.item_price) AS asin_revenue
FROM {schema}."{order_table}" o
JOIN {schema}.order_item oi
    ON o.order_id = oi.order_id
    AND oi.item_status != 'CANCELED'
JOIN {schema}.product_detail pd
    ON oi.product_detail_id = pd.product_detail_id
JOIN {schema}.product_asin pa
    ON pa.product_asin_id = pd.product_asin_id
    AND pa.client_id = o.client_id
WHERE o.client_id = {client_id}
    AND o.order_date >= CURRENT_DATE - INTERVAL '30 days'
    AND o.order_date < CURRENT_DATE
    AND o.order_status != 'CANCELED'
    AND o.sales_channel NOT IN ('Non-Amazon', 'Non-Amazon IN')
GROUP BY
    pa.asin,
    pd.categories ->> 'ProductCategoryId',
    pd.categories ->> 'ProductCategoryName'
ORDER BY asin_revenue DESC;
""".format(schema=sch, order_table=ord_tbl, client_id=client_id)

    with engine.connect() as conn:
        amazon_revenue_result = conn.execute(text(amazon_revenue_query)).fetchall()
        amazon_asin_wise_result = conn.execute(text(amazon_asin_wise_revenue_query)).fetchall()

    amazon_revenue = [dict(row._mapping) for row in amazon_revenue_result]
    amazon_asin_wise_revenue = [dict(row._mapping) for row in amazon_asin_wise_result]
    logger.info(
        "fetch_amazon_revenue_data: done for client_id=%s — amazon_revenue rows=%s, asin_wise rows=%s",
        client_id,
        len(amazon_revenue),
        len(amazon_asin_wise_revenue),
    )
    return {
        "amazon_revenue": amazon_revenue,
        "amazon_asin_wise_revenue": amazon_asin_wise_revenue,
    }


def _refine_query_with_llm(enriched_query: str, ltm_data: dict) -> Tuple[str, list[str]]:
    """
    Use an LLM to refine the enriched query by resolving vague references
    (e.g. "top selling ASIN", "low sales ASIN") using long-term memory data.
    Returns (refined_query, asins_to_use). On failure, returns (enriched_query, []).
    """
    from src.core.backend import invoke_gemini_with_tokens

    amazon_revenue = ltm_data.get("amazon_revenue") or []
    asin_wise = ltm_data.get("amazon_asin_wise_revenue") or []
    if not asin_wise:
        logger.debug("_refine_query_with_llm: skipping — no asin_wise data")
        return enriched_query, []

    logger.info(
        "long_term_memory: LLM refinement starting — query_len=%s, asin_wise_rows=%s",
        len(enriched_query),
        len(asin_wise),
    )

    system_prompt = """You refine user queries by resolving vague references using the provided long-term memory (revenue data).

Long-term memory context:
- amazon_revenue: revenue by sales_channel (e.g. Amazon.in, Amazon.com).
- amazon_asin_wise_revenue: list of rows with asin, category_id, category_name, asin_revenue (one row per asin per category), ordered by asin_revenue DESC. First item is top-selling (asin/category), last is lowest-selling.

Your task:
- If the query refers to "top selling", "best selling", "highest revenue" ASIN/product → use the ASIN(s) at the TOP of amazon_asin_wise_revenue.
- If the query refers to "low sales", "worst selling", "least selling", "lowest revenue" ASIN/product → use the ASIN(s) at the BOTTOM of amazon_asin_wise_revenue (excluding any with 0 revenue if there are others with non-zero revenue).
- Replace the vague phrase in the query with the concrete ASIN, e.g. "my top selling ASIN" → "ASIN B09PRH5Q49", "my low sales ASIN" → "ASIN B0D1XYZQJ7".
- Preserve the rest of the query unchanged (including marketplace mentions like "across amazon.in and amazon.com").
- If the query does not contain any reference that can be resolved from this data, return refined_query equal to the input query and asins as an empty list.

Output ONLY a single JSON object, no markdown or explanation:
{"refined_query": "<the refined query string>", "asins": ["<ASIN1>", "<ASIN2>"]}
Use an empty array for asins when no ASINs were resolved. refined_query must be the full sentence to use downstream."""

    user_content = f"""Current enriched query:
{enriched_query}

Long-term memory data (use this to resolve "top selling", "low sales", etc.):
amazon_revenue: {json.dumps(amazon_revenue, default=str)}
amazon_asin_wise_revenue (ordered by revenue DESC; first = top selling, last = lowest):
{json.dumps(asin_wise[:50] + asin_wise[-30:] if len(asin_wise) > 80 else asin_wise, default=str)}

Respond with only the JSON object."""

    try:
        response_text, in_tokens, out_tokens = invoke_gemini_with_tokens(
            formatted_messages=[{"role": "user", "content": user_content}],
            system_prompt=system_prompt,
            max_tokens=2000,
            temperature=0.1,
        )
        logger.info(
            "long_term_memory: LLM refinement call done — input_tokens=%s, output_tokens=%s, response_len=%s",
            in_tokens,
            out_tokens,
            len(response_text),
        )
    except Exception as e:
        logger.warning("long_term_memory: LLM refinement failed — %s", e, exc_info=True)
        return enriched_query, []

    # Parse JSON from response (allow markdown code block)
    text = response_text.strip()
    for pattern in (r"```(?:json)?\s*(\{.*?\})\s*```", r"(\{.*\})"):
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            try:
                parsed = json.loads(match.group(1))
                refined = (parsed.get("refined_query") or "").strip()
                llm_asins = parsed.get("asins")
                if isinstance(llm_asins, list):
                    asins_list = [str(a).strip() for a in llm_asins if a]
                else:
                    asins_list = []
                if refined:
                    logger.info(
                        "long_term_memory: LLM refinement applied — refined_query_len=%s, resolved_asins=%s",
                        len(refined),
                        asins_list,
                    )
                    logger.debug(
                        "long_term_memory: refined_query=%s",
                        refined[:120] + "..." if len(refined) > 120 else refined,
                    )
                    return refined, asins_list
            except (json.JSONDecodeError, TypeError) as parse_err:
                logger.debug("long_term_memory: JSON parse attempt failed: %s", parse_err)
                continue
    logger.warning(
        "long_term_memory: could not parse LLM refinement as JSON; response snippet=%s",
        response_text[:200] + "..." if len(response_text) > 200 else response_text,
    )
    return enriched_query, []


def enrich_query_with_ltm_context(
    enriched_query: str,
    payload: dict,
    asins: list[str],
    schema: str | None = None,
) -> Tuple[str, list[str]]:
    """
    Run long-term memory DB queries, then use an LLM to resolve references in the
    enriched query (e.g. "my top selling ASIN", "my low sales ASIN") using the
    fetched context. Returns the refined query and an updated asins list.

    Args:
        enriched_query: The current enriched query from user_intent (may contain
                        references like "my top selling ASIN" or "my low sales ASIN").
        payload: Dict that must contain "userId" (used as client_id for DB queries).
        asins: Current list of ASINs extracted from the query (may be empty).
        schema: Optional schema name; default from env AMAZON_SCHEMA.

    Returns:
        Tuple of (enriched_query, asins). enriched_query has references resolved
        using LTM data via LLM; asins may include resolved ASIN(s) when relevant.
    """
    user_id = payload.get("userId")
    logger.info(
        "enrich_query_with_ltm_context: entry — user_id=%s, enriched_query_len=%s, asins=%s",
        user_id,
        len(enriched_query),
        asins,
    )
    logger.debug(
        "enrich_query_with_ltm_context: enriched_query=%s",
        enriched_query[:150] + "..." if len(enriched_query) > 150 else enriched_query,
    )

    try:
        ltm_data = fetch_amazon_revenue_data(payload, schema)
    except (ValueError, Exception) as e:
        logger.warning(
            "enrich_query_with_ltm_context: fetch_amazon_revenue_data failed — %s; returning unchanged query",
            e,
        )
        return enriched_query, list(asins)

    asin_wise = ltm_data.get("amazon_asin_wise_revenue") or []
    if not asin_wise:
        logger.info(
            "enrich_query_with_ltm_context: no asin_wise data — skipping refinement, returning unchanged"
        )
        return enriched_query, list(asins)

    refined_query, resolved_asins = _refine_query_with_llm(enriched_query, ltm_data)
    updated_asins = list(asins)
    for a in resolved_asins:
        if a and a not in updated_asins:
            updated_asins.insert(0, a)

    logger.info(
        "enrich_query_with_ltm_context: done — refined_query_len=%s, updated_asins=%s",
        len(refined_query),
        updated_asins,
    )
    logger.debug(
        "enrich_query_with_ltm_context: refined_query=%s",
        refined_query[:150] + "..." if len(refined_query) > 150 else refined_query,
    )
    return refined_query.strip(), updated_asins


# Legacy constants (for backward compatibility if used elsewhere)
CLIENT_ID = 48

AMAZON_REVENUE = """
SELECT
o.sales_channel,
SUM(oi.item_price) AS revenue
FROM {schema}."{order_table}" o
JOIN {schema}."order_item" oi ON o.order_id = oi.order_id AND oi.item_status != 'CANCELED'
WHERE o.client_id = {client_id}
AND o.order_date >= CURRENT_DATE - INTERVAL '1 day'
AND o.order_date < CURRENT_DATE
AND o.order_status != 'CANCELED'
AND o.sales_channel NOT IN ('Non-Amazon', 'Non-Amazon IN')
GROUP BY o.sales_channel;
""".format(schema=DEFAULT_SCHEMA, order_table=ORDER_TABLE, client_id=CLIENT_ID)

AMAZON_ASIN_WISE_REVENUE = """
SELECT
    pa.asin,
    pd.categories ->> 'ProductCategoryId'   AS category_id,
    pd.categories ->> 'ProductCategoryName' AS category_name,
    SUM(oi.item_price) AS asin_revenue
FROM {schema}."{order_table}" o
JOIN {schema}.order_item oi
    ON o.order_id = oi.order_id
    AND oi.item_status != 'CANCELED'
JOIN {schema}.product_detail pd
    ON oi.product_detail_id = pd.product_detail_id
JOIN {schema}.product_asin pa
    ON pa.product_asin_id = pd.product_asin_id
    AND pa.client_id = o.client_id
WHERE o.client_id = {client_id}
    AND o.order_date >= CURRENT_DATE - INTERVAL '30 days'
    AND o.order_date < CURRENT_DATE
    AND o.order_status != 'CANCELED'
    AND o.sales_channel NOT IN ('Non-Amazon', 'Non-Amazon IN')
GROUP BY
    pa.asin,
    pd.categories ->> 'ProductCategoryId',
    pd.categories ->> 'ProductCategoryName'
ORDER BY asin_revenue DESC;
""".format(schema=DEFAULT_SCHEMA, order_table=ORDER_TABLE, client_id=CLIENT_ID)