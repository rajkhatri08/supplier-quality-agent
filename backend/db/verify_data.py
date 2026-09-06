"""Verify the seeded production data and re-measure the planted patterns.

The patterns moved when low-runner volumes were introduced, so the answer key
in docs/design-decisions.md is measured from this output rather than assumed.
"""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

pd.set_option("display.width", 140)
pd.set_option("display.max_columns", 20)

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
engine = create_engine(os.environ["DATABASE_URL"])

print("--- row counts ---")
print(pd.read_sql(
    "SELECT (SELECT COUNT(*) FROM suppliers)         AS suppliers, "
    "       (SELECT COUNT(*) FROM defect_codes)      AS codes, "
    "       (SELECT COUNT(*) FROM parts)             AS parts, "
    "       (SELECT COUNT(*) FROM production_volume) AS volume, "
    "       (SELECT COUNT(*) FROM defects)           AS defects, "
    "       (SELECT COUNT(*) FROM reports_8d)        AS reports", engine))

print("\n--- integrity (all must be 0) ---")
print(pd.read_sql(
    "SELECT (SELECT COUNT(*) FROM defects WHERE detected_date > CURRENT_DATE) "
    "         AS future_dated, "
    "       (SELECT COUNT(*) FROM defects d LEFT JOIN parts p "
    "        ON p.part_id = d.part_id WHERE p.part_id IS NULL) AS orphans, "
    "       (SELECT COUNT(*) FROM ("
    "          SELECT part_id FROM production_volume "
    "          GROUP BY part_id HAVING COUNT(*) <> 24) x) AS bad_month_counts",
    engine))

print("\n--- low runners ---")
print(pd.read_sql(
    "SELECT v.part_id, p.part_name, "
    "       ROUND(AVG(v.units_produced)) AS avg_units, "
    "       COUNT(DISTINCT d.m) AS months_with_defects "
    "FROM production_volume v "
    "JOIN parts p ON p.part_id = v.part_id "
    "LEFT JOIN (SELECT part_id, date_trunc('month', detected_date)::date AS m "
    "           FROM defects GROUP BY 1, 2) d "
    "  ON d.part_id = v.part_id AND d.m = v.month "
    "WHERE v.part_id IN ('PN-1006','PN-1023','PN-1031','PN-1044','PN-1050') "
    "GROUP BY v.part_id, p.part_name ORDER BY v.part_id", engine))

print("\n--- PATTERN 1: SUP-003 PPM by month ---")
print(pd.read_sql(
    "SELECT v.month, SUM(v.units_produced) AS units, "
    "       COALESCE(SUM(d.qty), 0) AS defect_units, "
    "       ROUND(COALESCE(SUM(d.qty),0) * 1000000.0 / SUM(v.units_produced), 0) AS ppm "
    "FROM production_volume v "
    "JOIN parts p ON p.part_id = v.part_id "
    "LEFT JOIN (SELECT part_id, date_trunc('month', detected_date)::date AS m, "
    "                  SUM(quantity) AS qty FROM defects GROUP BY 1, 2) d "
    "  ON d.part_id = v.part_id AND d.m = v.month "
    "WHERE p.supplier_id = 'SUP-003' "
    "GROUP BY v.month ORDER BY v.month", engine))

print("\n--- PATTERN 2: PN-1042 by month ---")
print(pd.read_sql(
    "SELECT date_trunc('month', detected_date)::date AS month, "
    "       COUNT(*) AS events, SUM(quantity) AS units "
    "FROM defects WHERE part_id = 'PN-1042' GROUP BY 1 ORDER BY 1", engine))

print("\n--- PATTERN 3: D-WLD-01 by supplier ---")
print(pd.read_sql(
    "SELECT p.supplier_id, COUNT(*) AS events, "
    "       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct "
    "FROM defects d JOIN parts p ON p.part_id = d.part_id "
    "WHERE d.defect_code = 'D-WLD-01' "
    "GROUP BY p.supplier_id ORDER BY events DESC", engine))

print("\n--- 8D reports ---")
print(pd.read_sql(
    "SELECT status, COUNT(*) AS n FROM reports_8d GROUP BY status", engine))
print(pd.read_sql(
    "SELECT report_id, supplier_id, defect_code, opened_date, status "
    "FROM reports_8d WHERE supplier_id = 'SUP-003' ORDER BY opened_date",
    engine))