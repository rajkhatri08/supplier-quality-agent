import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

SPIKE_DIR = Path(__file__).resolve().parent
load_dotenv(SPIKE_DIR.parent / ".env")

sql = (SPIKE_DIR / "schema.sql").read_text()

engine = create_engine(os.environ["DATABASE_URL"])

with engine.begin() as conn:
    conn.execute(text(sql))

print("schema applied")
