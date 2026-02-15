"""
Test script to execute PostgreSQL query using psycopg2 and credentials from .env.
"""

import os
import sys
from urllib.parse import urlparse, urlunparse

from dotenv import load_dotenv
import psycopg2
from psycopg2 import OperationalError

load_dotenv()

QUERY = """
SELECT pa.* FROM amazon.product_asin AS pa
WHERE pa.client_id = 48
ORDER BY pa.client_id;
"""

DB_NAME = "ms_mp_prod"


def main() -> None:
    db_url = os.getenv("DATABASE_URL_PRODUCTION")
    if not db_url:
        print("ERROR: DATABASE_URL_PRODUCTION not found in .env")
        sys.exit(1)

    parsed = urlparse(db_url)
    url_ms_mp = urlunparse((
        parsed.scheme, parsed.netloc, f"/{DB_NAME}",
        parsed.params, parsed.query, parsed.fragment
    ))

    try:
        conn = psycopg2.connect(url_ms_mp)
    except OperationalError as e:
        print(f"ERROR: Failed to connect to PostgreSQL: {e}")
        sys.exit(1)

    try:
        with conn.cursor() as cur:
            cur.execute(QUERY)
            rows = cur.fetchall()
            colnames = [desc[0] for desc in cur.description]
            print("Columns:", colnames)
            print("-" * 60)
            for row in rows:
                print(row)
            print("-" * 60)
            print(f"Total rows: {len(rows)}")
    finally:
        conn.close()
        print("Connection closed.")


if __name__ == "__main__":
    main()
