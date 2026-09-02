import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
engine = create_engine(os.environ["DATABASE_URL"])

with engine.connect() as conn:
    tables = conn.execute(text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'spike' ORDER BY table_name"
    )).scalars().all()

    fks = conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.table_constraints "
        "WHERE table_schema = 'spike' AND constraint_type = 'FOREIGN KEY'"
    )).scalar()

print("tables:", tables)
print("foreign keys:", fks)
