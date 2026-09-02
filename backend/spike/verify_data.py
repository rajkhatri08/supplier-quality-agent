import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
engine = create_engine(os.environ["DATABASE_URL"])

print(pd.read_sql("SELECT COUNT(*) AS n FROM spike.suppliers", engine))
print(pd.read_sql(
    "SELECT commodity, COUNT(*) AS n FROM spike.suppliers "
    "GROUP BY commodity ORDER BY commodity", engine))
print(pd.read_sql(
    "SELECT * FROM spike.suppliers WHERE supplier_id = 'SUP-003'", engine))