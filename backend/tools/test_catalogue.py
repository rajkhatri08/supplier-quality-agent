"""Run every catalogue query with known-good parameters.

No LLM involved — this checks the SQL itself before anything selects between
the queries. Numbers are compared against the answer key in
docs/design-decisions.md.
"""

import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.query_catalogue import CATALOGUE  # noqa: E402

pd.set_option("display.width", 140)
pd.set_option("display.max_columns", 20)

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
engine = create_engine(os.environ["DATABASE_URL"])

CASES = [
    ("supplier_ppm_over_window", {"supplier_id": "SUP-003",
                                  "start_month": date(2026, 3, 1),
                                  "end_month": date(2026, 8, 1)}),
    ("supplier_ppm_by_month",    {"supplier_id": "SUP-003",
                                  "start_month": date(2026, 3, 1),
                                  "end_month": date(2026, 8, 1)}),
    ("supplier_ppm_ranking",     {"start_month": date(2025, 9, 1),
                                  "end_month": date(2026, 8, 1)}),
    ("defect_code_breakdown",    {"supplier_id": "SUP-003",
                                  "start_date": date(2024, 9, 1),
                                  "end_date": date(2026, 8, 31)}),
    ("part_ppm_ranking",         {"start_month": date(2025, 9, 1),
                                  "end_month": date(2026, 8, 1)}),
    ("defect_code_by_supplier",  {"defect_code": "D-WLD-01",
                                  "start_date": date(2024, 9, 1),
                                  "end_date": date(2026, 8, 31)}),
    ("severity_breakdown",       {"supplier_id": "SUP-003",
                                  "start_date": date(2024, 9, 1),
                                  "end_date": date(2026, 8, 31)}),
    ("parts_without_defects",    {"start_month": date(2026, 8, 1),
                                  "end_month": date(2026, 8, 1)}),
]

for query_id, params in CASES:
    entry = CATALOGUE[query_id]
    print(f"\n{'=' * 70}\n{query_id}\n{params}\n{'=' * 70}")
    with engine.connect() as conn:
        df = pd.read_sql(text(entry.sql), conn, params=params)
    print(df.head(8).to_string(index=False))
    print(f"({len(df)} rows)")