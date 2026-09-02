import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
engine = create_engine(os.environ["DATABASE_URL"])

print("--- row counts ---")
print(pd.read_sql(
    "SELECT (SELECT COUNT(*) FROM spike.suppliers)    AS suppliers, "
    "       (SELECT COUNT(*) FROM spike.defect_codes) AS defect_codes, "
    "       (SELECT COUNT(*) FROM spike.parts)        AS parts", engine))

print("\n--- defect codes by severity ---")
print(pd.read_sql(
    "SELECT severity, COUNT(*) AS n FROM spike.defect_codes "
    "GROUP BY severity ORDER BY severity", engine))

print("\n--- D-WLD-01 (concentration code) ---")
print(pd.read_sql(
    "SELECT * FROM spike.defect_codes WHERE defect_code = 'D-WLD-01'", engine))

print("\n--- PN-1042 (spike part) ---")
print(pd.read_sql(
    "SELECT p.part_id, p.part_name, p.supplier_id, p.vehicle_system "
    "FROM spike.parts p WHERE p.part_id = 'PN-1042'", engine))