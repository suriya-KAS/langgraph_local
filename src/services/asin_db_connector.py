"""
ASIN DB Connector - Fetches product_asin data from PostgreSQL.

Uses client_id (UserID from frontend) to scope the query.
No hardcoded client_id - always taken from the request payload.
"""
import os
import asyncio
from typing import Optional
from urllib.parse import urlparse, urlunparse

from dotenv import load_dotenv
import psycopg2
from psycopg2 import OperationalError
from psycopg2.extras import RealDictCursor

from utils.logger_config import get_logger

load_dotenv()
logger = get_logger(__name__)

DB_NAME = "ms_mp_prod"

# All product_asin rows for a client (no ASIN filter)
QUERY = """
SELECT pa.* FROM amazon.product_asin AS pa
WHERE pa.client_id = %s
ORDER BY pa.client_id;
"""

# Single product_asin row for a client + ASIN (client_id and asin from orchestrator/payload)
QUERY_BY_CLIENT_AND_ASIN = """
SELECT pa.*
FROM amazon.product_asin AS pa
WHERE pa.client_id = %s
  AND pa.asin = %s;
"""

# All product_detail rows for a given product_asin_id (fetched dynamically from product_asin)
QUERY_PRODUCT_DETAIL_BY_PRODUCT_ASIN_ID = """
SELECT pd.* FROM amazon.product_detail AS pd
WHERE pd.product_asin_id = %s;
"""


def _normalize_client_id(client_id) -> Optional[int]:
    """
    Normalize client_id from frontend payload (userId) to int.
    Returns None if invalid.
    """
    if client_id is None:
        return None
    if isinstance(client_id, int):
        return client_id if client_id >= 1 else None
    if isinstance(client_id, str):
        try:
            n = int(client_id.strip())
            return n if n >= 1 else None
        except ValueError:
            return None
    return None


def _get_connection():
    """Build connection URL and connect to PostgreSQL (ms_mp_prod)."""
    db_url = os.getenv("DATABASE_URL_PRODUCTION")
    if not db_url:
        raise ValueError("DATABASE_URL_PRODUCTION not found in environment")
    parsed = urlparse(db_url)
    url_ms_mp = urlunparse((
        parsed.scheme, parsed.netloc, f"/{DB_NAME}",
        parsed.params, parsed.query, parsed.fragment
    ))
    return psycopg2.connect(url_ms_mp)


def fetch_product_asin(client_id) -> dict:
    """
    Execute product_asin query for the given client_id (UserID from frontend).

    Args:
        client_id: User ID from frontend payload (context.userId).
                   Can be int or str; will be normalized to int.

    Returns:
        {
            "success": bool,
            "columns": list[str] | None,
            "rows": list[dict] | list[tuple] | None,
            "row_count": int,
            "error": str | None
        }
    """
    normalized = _normalize_client_id(client_id)
    if normalized is None:
        logger.warning(f"Invalid or missing client_id: {client_id}")
        return {
            "success": False,
            "columns": None,
            "rows": None,
            "row_count": 0,
            "error": f"Invalid or missing client_id: {client_id}",
        }

    try:
        conn = _get_connection()
    except (ValueError, OperationalError) as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        return {
            "success": False,
            "columns": None,
            "rows": None,
            "row_count": 0,
            "error": str(e),
        }

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(QUERY, (normalized,))
            rows = cur.fetchall()
            colnames = [desc[0] for desc in cur.description]
            # Convert RealDictRow to plain dict for JSON-serializable output
            rows_serializable = [dict(r) for r in rows]
            logger.info(f"Fetched {len(rows_serializable)} product_asin rows for client_id={normalized}")
            return {
                "success": True,
                "columns": colnames,
                "rows": rows_serializable,
                "row_count": len(rows_serializable),
                "error": None,
            }
    except Exception as e:
        logger.error(f"Query failed for client_id={normalized}: {e}", exc_info=True)
        return {
            "success": False,
            "columns": None,
            "rows": None,
            "row_count": 0,
            "error": str(e),
        }
    finally:
        conn.close()


def fetch_product_asin_by_client_and_asin(client_id, asin: str) -> dict:
    """
    Fetch product_asin row(s) for the given client_id and ASIN.
    client_id comes from payload (userId); asin comes from orchestrator (insights_asin_id).

    Args:
        client_id: User ID from frontend payload (context.userId). Can be int or str.
        asin: ASIN string (e.g. 'B0C45C6RZS'). From classifier/orchestrator.

    Returns:
        Same shape as fetch_product_asin: success, columns, rows, row_count, error.
    """
    normalized = _normalize_client_id(client_id)
    if normalized is None:
        logger.warning(f"Invalid or missing client_id: {client_id}")
        return {
            "success": False,
            "columns": None,
            "rows": None,
            "row_count": 0,
            "error": f"Invalid or missing client_id: {client_id}",
        }
    asin_str = (asin or "").strip()
    if not asin_str:
        logger.warning("Missing asin for fetch_product_asin_by_client_and_asin")
        return {
            "success": False,
            "columns": None,
            "rows": None,
            "row_count": 0,
            "error": "Missing asin",
        }

    try:
        conn = _get_connection()
    except (ValueError, OperationalError) as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        return {
            "success": False,
            "columns": None,
            "rows": None,
            "row_count": 0,
            "error": str(e),
        }

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(QUERY_BY_CLIENT_AND_ASIN, (normalized, asin_str))
            rows = cur.fetchall()
            colnames = [desc[0] for desc in cur.description]
            rows_serializable = [dict(r) for r in rows]
            logger.info(
                f"Fetched {len(rows_serializable)} product_asin row(s) for client_id={normalized}, asin={asin_str}"
            )
            return {
                "success": True,
                "columns": colnames,
                "rows": rows_serializable,
                "row_count": len(rows_serializable),
                "error": None,
            }
    except Exception as e:
        logger.error(
            f"Query failed for client_id={normalized}, asin={asin_str}: {e}",
            exc_info=True,
        )
        return {
            "success": False,
            "columns": None,
            "rows": None,
            "row_count": 0,
            "error": str(e),
        }
    finally:
        conn.close()


def fetch_product_detail_by_client_and_asin(client_id, asin: str) -> dict:
    """
    When ASIN is present: fetch product_asin_id from product_asin, then fetch all
    product_detail rows for that product_asin_id.

    Args:
        client_id: User ID from frontend payload (context.userId). Can be int or str.
        asin: ASIN string (e.g. 'B0C45C6RZS'). From classifier/orchestrator.

    Returns:
        Same shape as fetch_product_asin: success, columns, rows, row_count, error.
        rows contain product_detail data when product_asin_id is found.
    """
    # Step 1: Fetch product_asin to get product_asin_id
    pa_result = fetch_product_asin_by_client_and_asin(client_id, asin)
    if not pa_result.get("success") or not pa_result.get("rows"):
        return pa_result

    rows_pa = pa_result["rows"]
    first_row = rows_pa[0]
    # product_asin_id can be the column name; fallback to id if needed
    product_asin_id = first_row.get("product_asin_id") or first_row.get("id")
    if product_asin_id is None:
        logger.warning(f"product_asin row has no product_asin_id or id: {first_row}")
        return {
            "success": False,
            "columns": None,
            "rows": None,
            "row_count": 0,
            "error": "product_asin_id not found in product_asin row",
        }

    try:
        conn = _get_connection()
    except (ValueError, OperationalError) as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        return {
            "success": False,
            "columns": None,
            "rows": None,
            "row_count": 0,
            "error": str(e),
        }

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(QUERY_PRODUCT_DETAIL_BY_PRODUCT_ASIN_ID, (product_asin_id,))
            rows = cur.fetchall()
            colnames = [desc[0] for desc in cur.description]
            rows_serializable = [dict(r) for r in rows]
            logger.info(
                f"Fetched {len(rows_serializable)} product_detail row(s) for product_asin_id={product_asin_id}"
            )
            return {
                "success": True,
                "columns": colnames,
                "rows": rows_serializable,
                "row_count": len(rows_serializable),
                "error": None,
            }
    except Exception as e:
        logger.error(
            f"product_detail query failed for product_asin_id={product_asin_id}: {e}",
            exc_info=True,
        )
        return {
            "success": False,
            "columns": None,
            "rows": None,
            "row_count": 0,
            "error": str(e),
        }
    finally:
        conn.close()


async def fetch_product_asin_async(client_id) -> dict:
    """
    Async wrapper for fetch_product_asin. Use from async category handlers.

    Args:
        client_id: User ID from frontend payload (context.userId).

    Returns:
        Same dict as fetch_product_asin.
    """
    return await asyncio.to_thread(fetch_product_asin, client_id)


async def fetch_product_asin_by_client_and_asin_async(client_id, asin: str) -> dict:
    """
    Async wrapper for fetch_product_asin_by_client_and_asin. Use from async category handlers
    when handling insights_kb ASIN flow (userId from payload, asin from orchestrator).

    Args:
        client_id: User ID from frontend payload (context.userId).
        asin: ASIN from classifier/orchestrator (context.insights_asin_id).

    Returns:
        Same dict as fetch_product_asin_by_client_and_asin.
    """
    return await asyncio.to_thread(fetch_product_asin_by_client_and_asin, client_id, asin)


async def fetch_product_detail_by_client_and_asin_async(client_id, asin: str) -> dict:
    """
    Async wrapper for fetch_product_detail_by_client_and_asin. Use when ASIN is present
    and you need product_detail data (product_asin_id resolved internally).

    Args:
        client_id: User ID from frontend payload (context.userId).
        asin: ASIN from classifier/orchestrator (context.insights_asin_id).

    Returns:
        Same dict as fetch_product_detail_by_client_and_asin.
    """
    return await asyncio.to_thread(fetch_product_detail_by_client_and_asin, client_id, asin)


if __name__ == "__main__":
    """CLI: Fetch product_asin for a client_id. Usage: python -m src.services.asin_db_connector <client_id>"""
    import sys
    client_id = sys.argv[1] if len(sys.argv) > 1 else os.getenv("CLIENT_ID", "48")
    result = fetch_product_asin(client_id)
    print("Columns:", result.get("columns"))
    print("-" * 60)
    for row in (result.get("rows") or []):
        print(row)
    print("-" * 60)
    print(f"Total rows: {result.get('row_count', 0)}")
    if result.get("error"):
        print("Error:", result["error"])
        sys.exit(1)
