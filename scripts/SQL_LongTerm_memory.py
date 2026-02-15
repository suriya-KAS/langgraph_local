



import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()  # loads DATABASE_URL from .env

engine = create_engine(os.environ["DATABASE_URL_PRODUCTION"])

query = text("""
SELECT cm.clientrevenue_id  FROM clients.client_master AS cm
where cm.client_id = 48
ORDER BY cm.clientrevenue_id
""")

with engine.connect() as conn:
    output = conn.execute(query)
    for i in output:
        print(i)
