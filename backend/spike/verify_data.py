import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
engine = create_engine(os.environ["DATABASE_URL"])

print("--- row counts ---")
print(pd.read_sql(
    "SELECT (SELECT COUNT(*) FROM spike.suppliers) AS suppliers, "
    "       (SELECT COUNT(*) FROM spike.parts) AS parts", engine))

print("\n--- parts per supplier ---")
print(pd.read_sql(
    "SELECT s.supplier_id, s.commodity, COUNT(p.part_id) AS parts "
    "FROM spike.suppliers s "
    "LEFT JOIN spike.parts p ON p.supplier_id = s.supplier_id "
    "GROUP BY s.supplier_id, s.commodity ORDER BY s.supplier_id", engine))

print("\n--- SUP-003 parts (trend supplier) ---")
print(pd.read_sql(
    "SELECT part_id, part_name, vehicle_system FROM spike.parts "
    "WHERE supplier_id = 'SUP-003' ORDER BY part_id", engine))

print("\n--- PN-1042 (answer key spike part) ---")
print(pd.read_sql(
    "SELECT p.*, s.commodity FROM spike.parts p "
    "JOIN spike.suppliers s ON s.supplier_id = p.supplier_id "
    "WHERE p.part_id = 'PN-1042'", engine))