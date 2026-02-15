"""
ASIN DB Connector - Fetches product_asin data from PostgreSQL.

Uses client_id (UserID from frontend) to scope the query.
No hardcoded client_id - always taken from the request payload.

When the user query contains ASIN(s), the validator checks whether each ASIN
belongs to the client (exists in amazon.product_asin for that client_id).
"""
import os
from typing import Optional, List, Tuple, Union
from urllib.parse import urlparse, urlunparse

from dotenv import load_dotenv
import psycopg2
from psycopg2 import OperationalError
from psycopg2.extras import RealDictCursor

from utils.logger_config import get_logger

load_dotenv()
logger = get_logger(__name__)

DB_NAME = "ms_mp_prod"

ASIN_VALIDATOR_QUERY = """SELECT pa.*
FROM amazon.product_asin AS pa
WHERE pa.client_id = %s
  AND pa.asin = %s;"""

# Use LOWER() so ASIN matching is case-insensitive (DB may store lowercase)
ASIN_EXISTS_QUERY = """SELECT COUNT(*) FROM amazon.product_asin WHERE client_id = %s AND LOWER(TRIM(asin)) = LOWER(TRIM(%s));"""

# Max ASINs to return when listing client's catalog (for "incorrect ASIN" response)
CLIENT_ASINS_LIST_LIMIT = 10

CLIENT_ASINS_QUERY = """SELECT asin FROM amazon.product_asin WHERE client_id = %s ORDER BY LOWER(asin) LIMIT %s;"""


def _get_connection():
    """Open a connection to the ms_mp_prod PostgreSQL database."""
    db_url = os.getenv("DATABASE_URL_PRODUCTION")
    if not db_url:
        raise ValueError("DATABASE_URL_PRODUCTION is not set")
    parsed = urlparse(db_url)
    url_ms_mp = urlunparse((
        parsed.scheme, parsed.netloc, f"/{DB_NAME}",
        parsed.params, parsed.query, parsed.fragment
    ))
    return psycopg2.connect(url_ms_mp)


def _normalize_client_id(client_id: Union[str, int]) -> int:
    """Convert client_id to int for DB query (client_id in DB is integer)."""
    if isinstance(client_id, int):
        return client_id
    try:
        return int(client_id)
    except (TypeError, ValueError):
        raise ValueError(f"client_id must be a number, got: {client_id!r}")


def validate_asin_for_client(client_id: Union[str, int], asin: str) -> bool:
    """
    Check whether the given ASIN belongs to the client (exists in amazon.product_asin).

    Args:
        client_id: Client/user ID from the request (userId from frontend).
        asin: ASIN string to validate.

    Returns:
        True if the ASIN exists for this client_id, False otherwise.
    """
    if not asin or not str(asin).strip():
        return False
    asin = str(asin).strip()
    cid = _normalize_client_id(client_id)
    conn = None
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(ASIN_EXISTS_QUERY, (cid, asin))
            row = cur.fetchone()
            count = row[0] if row else 0
            return count > 0
    except (ValueError, OperationalError) as e:
        logger.warning(f"ASIN validation failed for client_id={client_id}, asin={asin!r}: {e}")
        return False
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def validate_asins_for_client(
    client_id: Union[str, int],
    asins: List[str],
) -> Tuple[List[str], List[str]]:
    """
    Split ASINs into those that belong to the client and those that do not.

    Args:
        client_id: Client/user ID from the request.
        asins: List of ASIN strings to validate.

    Returns:
        (valid_asins, invalid_asins) — ASINs that belong to the client and those that do not.
    """
    if not asins:
        return [], []
    valid: List[str] = []
    invalid: List[str] = []
    for a in asins:
        s = str(a).strip()
        if not s:
            continue
        if validate_asin_for_client(client_id, s):
            valid.append(s)
        else:
            invalid.append(s)
    return valid, invalid


def get_client_asins(client_id: Union[str, int], limit: int = CLIENT_ASINS_LIST_LIMIT) -> List[str]:
    """
    Fetch all ASINs associated with the client from amazon.product_asin.

    Used when the user provides invalid ASIN(s) so we can show them their
    actual listed ASINs (e.g. "These are your actual listed ASINs, select one or enter a correct ASIN").

    Args:
        client_id: Client/user ID from the request (userId from frontend).
        limit: Max number of ASINs to return (default CLIENT_ASINS_LIST_LIMIT).

    Returns:
        List of ASIN strings for this client (possibly empty on error or no data).
    """
    try:
        cid = _normalize_client_id(client_id)
    except ValueError as e:
        logger.warning(f"get_client_asins invalid client_id: {e}")
        return []
    conn = None
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(CLIENT_ASINS_QUERY, (cid, limit))
            rows = cur.fetchall()
            return [row[0] for row in rows if row and row[0]]
    except (ValueError, OperationalError) as e:
        logger.warning(f"get_client_asins failed for client_id={client_id}: {e}")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

