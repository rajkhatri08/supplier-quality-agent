import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
engine = create_engine(os.environ["DATABASE_URL"])

print("--- row counts ---")
print(pd.read_sql(
    "SELECT (SELECT COUNT(*) FROM spike.suppliers)         AS suppliers, "
    "       (SELECT COUNT(*) FROM spike.defect_codes)      AS defect_codes, "
    "       (SELECT COUNT(*) FROM spike.parts)             AS parts, "
    "       (SELECT COUNT(*) FROM spike.production_volume) AS volume", engine))

print("\n--- month coverage ---")
print(pd.read_sql(
    "SELECT MIN(month) AS first_month, MAX(month) AS last_month, "
    "       COUNT(DISTINCT month) AS distinct_months, "
    "       COUNT(DISTINCT part_id) AS distinct_parts "
    "FROM spike.production_volume", engine))

print("\n--- integrity checks (all must be 0) ---")
print(pd.read_sql(
    "SELECT (SELECT COUNT(*) FROM spike.production_volume WHERE units_produced <= 0) "
    "         AS non_positive_units, "
    "       (SELECT COUNT(*) FROM spike.production_volume v "
    "        LEFT JOIN spike.parts p ON p.part_id = v.part_id "
    "        WHERE p.part_id IS NULL) AS orphan_volume_rows, "
    "       (SELECT COUNT(*) FROM ("
    "          SELECT part_id FROM spike.production_volume "
    "          GROUP BY part_id HAVING COUNT(*) <> 24) x) AS parts_not_24_months",
    engine))

print("\n--- monthly volume by commodity ---")
print(pd.read_sql(
    "SELECT s.commodity, "
    "       MIN(v.units_produced) AS min_units, "
    "       ROUND(AVG(v.units_produced)) AS avg_units, "
    "       MAX(v.units_produced) AS max_units "
    "FROM spike.production_volume v "
    "JOIN spike.parts p     ON p.part_id = v.part_id "
    "JOIN spike.suppliers s ON s.supplier_id = p.supplier_id "
    "GROUP BY s.commodity ORDER BY avg_units", engine))

print("\n--- annual volume per supplier (last 12 months) ---")
print(pd.read_sql(
    "SELECT s.supplier_id, s.commodity, "
    "       SUM(v.units_produced) AS units_12m "
    "FROM spike.production_volume v "
    "JOIN spike.parts p     ON p.part_id = v.part_id "
    "JOIN spike.suppliers s ON s.supplier_id = p.supplier_id "
    "WHERE v.month >= DATE '2025-09-01' "
    "GROUP BY s.supplier_id, s.commodity ORDER BY units_12m DESC", engine))