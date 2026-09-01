import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

url = os.environ["DATABASE_URL"]
engine = create_engine(url)

with engine.connect() as conn:
    version = conn.execute(text("SELECT version()")).scalar()
    schema = conn.execute(
        text(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name = 'spike'"
        )
    ).scalar()

print("connected")
print("postgres:", version.split(",")[0])
print("spike schema:", schema)