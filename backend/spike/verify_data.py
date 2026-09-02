import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

pd.set_option("display.width", 120)
pd.set_option("display.max_columns", 20)

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
engine = create_engine(os.environ["DATABASE_URL"])

print("--- row counts ---")
print(pd.read_sql(
    "SELECT (SELECT COUNT(*) FROM spike.suppliers)         AS suppliers, "
    "       (SELECT COUNT(*) FROM spike.defect_codes)      AS defect_codes, "
    "       (SELECT COUNT(*) FROM spike.parts)             AS parts, "
    "       (SELECT COUNT(*) FROM spike.production_volume) AS volume, "
    "       (SELECT COUNT(*) FROM spike.defects)           AS defects", engine))

print("\n--- integrity checks (all must be 0) ---")
print(pd.read_sql(
    "SELECT (SELECT COUNT(*) FROM spike.defects WHERE quantity <= 0) "
    "         AS non_positive_qty, "
    "       (SELECT COUNT(*) FROM spike.defects WHERE detected_date > CURRENT_DATE) "
    "         AS future_dated, "
    "       (SELECT COUNT(*) FROM spike.defects d "
    "        LEFT JOIN spike.parts p ON p.part_id = d.part_id "
    "        WHERE p.part_id IS NULL) AS orphan_defects, "
    "       (SELECT COUNT(*) FROM ("
    "          SELECT d.part_id, date_trunc('month', d.detected_date) AS m, "
    "                 SUM(d.quantity) AS q "
    "          FROM spike.defects d GROUP BY 1, 2) x "
    "        JOIN spike.production_volume v "
    "          ON v.part_id = x.part_id AND v.month = x.m "
    "        WHERE x.q > v.units_produced) AS qty_exceeds_volume",
    engine))

print("\n--- PATTERN 1: SUP-003 PPM by month (trend) ---")
print(pd.read_sql(
    "SELECT v.month, "
    "       SUM(v.units_produced) AS units, "
    "       COALESCE(SUM(d.qty), 0) AS defect_units, "
    "       ROUND(COALESCE(SUM(d.qty), 0) * 1000000.0 "
    "             / SUM(v.units_produced), 0) AS ppm "
    "FROM spike.production_volume v "
    "JOIN spike.parts p ON p.part_id = v.part_id "
    "LEFT JOIN (SELECT part_id, date_trunc('month', detected_date) AS m, "
    "                  SUM(quantity) AS qty "
    "           FROM spike.defects GROUP BY 1, 2) d "
    "  ON d.part_id = v.part_id AND d.m = v.month "
    "WHERE p.supplier_id = 'SUP-003' "
    "GROUP BY v.month ORDER BY v.month", engine))

print("\n--- PATTERN 2: PN-1042 defect events by month (spike) ---")
print(pd.read_sql(
    "SELECT date_trunc('month', detected_date)::date AS month, "
    "       COUNT(*) AS events, SUM(quantity) AS defect_units "
    "FROM spike.defects WHERE part_id = 'PN-1042' "
    "GROUP BY 1 ORDER BY 1", engine))

print("\n--- PATTERN 3: D-WLD-01 by supplier (concentration) ---")
print(pd.read_sql(
    "SELECT p.supplier_id, COUNT(*) AS events, "
    "       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct "
    "FROM spike.defects d "
    "JOIN spike.parts p ON p.part_id = d.part_id "
    "WHERE d.defect_code = 'D-WLD-01' "
    "GROUP BY p.supplier_id ORDER BY events DESC", engine))