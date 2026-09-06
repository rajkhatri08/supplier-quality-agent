"""Test parameter validation: what should pass, and what should fail."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.query_params import parse_query_call  # noqa: E402

SHOULD_PASS = [
    {"query_id": "supplier_ppm_by_month", "supplier_id": "SUP-003",
     "start_month": "2026-03-01", "end_month": "2026-08-01"},
    {"query_id": "supplier_ppm_ranking",
     "start_month": "2025-09-01", "end_month": "2026-08-01"},
    {"query_id": "defect_code_by_supplier", "defect_code": "D-WLD-01",
     "start_date": "2024-09-01", "end_date": "2026-08-31"},
]

SHOULD_FAIL = [
    ("unknown query",
     {"query_id": "supplier_delivery_rate", "supplier_id": "SUP-003"}),
    ("malformed supplier id",
     {"query_id": "supplier_ppm_by_month", "supplier_id": "SUP-3",
      "start_month": "2026-03-01", "end_month": "2026-08-01"}),
    ("lowercase supplier id",
     {"query_id": "supplier_ppm_by_month", "supplier_id": "sup-003",
      "start_month": "2026-03-01", "end_month": "2026-08-01"}),
    ("month not first of month",
     {"query_id": "supplier_ppm_by_month", "supplier_id": "SUP-003",
      "start_month": "2026-03-15", "end_month": "2026-08-01"}),
    ("start after end",
     {"query_id": "supplier_ppm_by_month", "supplier_id": "SUP-003",
      "start_month": "2026-08-01", "end_month": "2026-03-01"}),
    ("range outside data window",
     {"query_id": "supplier_ppm_by_month", "supplier_id": "SUP-003",
      "start_month": "2020-01-01", "end_month": "2020-12-01"}),
    ("sql injection attempt",
     {"query_id": "supplier_ppm_by_month",
      "supplier_id": "SUP-003'; DROP TABLE parts; --",
      "start_month": "2026-03-01", "end_month": "2026-08-01"}),
    ("missing parameter",
     {"query_id": "supplier_ppm_by_month", "supplier_id": "SUP-003",
      "start_month": "2026-03-01"}),
]

print("--- should pass ---")
for payload in SHOULD_PASS:
    call = parse_query_call(payload)
    print(f"  ok   {call.query_id}")

print("\n--- should fail ---")
for label, payload in SHOULD_FAIL:
    try:
        parse_query_call(payload)
        print(f"  MISS {label}: accepted, should have been rejected")
    except Exception as e:
        first_line = str(e).split("\n")[0]
        print(f"  ok   {label}: {first_line[:70]}")