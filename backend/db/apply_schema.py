"""Apply the production schema to Neon.

Drops and recreates all tables in the public schema. Destructive by design —
the generator reseeds from scratch.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

DB_DIR = Path(__file__).resolve().parent
load_dotenv(DB_DIR.parent / ".env")

sql = (DB_DIR / "schema.sql").read_text()
engine = create_engine(os.environ["DATABASE_URL"])

with engine.begin() as conn:
    conn.execute(text(sql))

print("schema applied")