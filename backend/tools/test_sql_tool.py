"""End-to-end tool tests: valid calls, and all three decline paths."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.sql_tool import run_query, catalogue_manifest  # noqa: E402

CASES = [
    ("valid — SUP-003 trend",
     {"query_id": "supplier_ppm_by_month", "supplier_id": "SUP-003",
      "start_month": "2026-03-01", "end_month": "2026-08-01"}),

    ("valid — D-WLD-01 concentration",
     {"query_id": "defect_code_by_supplier", "defect_code": "D-WLD-01",
      "start_date": "2024-09-01", "end_date": "2026-08-31"}),

    ("valid — parts without defects",
     {"query_id": "parts_without_defects",
      "start_month": "2026-08-01", "end_month": "2026-08-01"}),

    ("decline — unknown query",
     {"query_id": "supplier_delivery_rate", "supplier_id": "SUP-003"}),

    ("decline — supplier does not exist",
     {"query_id": "supplier_ppm_by_month", "supplier_id": "SUP-011",
      "start_month": "2026-03-01", "end_month": "2026-08-01"}),

    ("decline — malformed id",
     {"query_id": "supplier_ppm_by_month", "supplier_id": "sup-3",
      "start_month": "2026-03-01", "end_month": "2026-08-01"}),

    ("decline — month not first of month",
     {"query_id": "supplier_ppm_by_month", "supplier_id": "SUP-003",
      "start_month": "2026-03-15", "end_month": "2026-08-01"}),

    ("decline — outside data window",
     {"query_id": "supplier_ppm_by_month", "supplier_id": "SUP-003",
      "start_month": "2020-01-01", "end_month": "2020-12-01"}),
]

print("--- catalogue manifest (what the agent sees) ---")
for entry in catalogue_manifest():
    print(f"  {entry['query_id']}")
    print(f"    params: {', '.join(entry['params'])}")

for label, payload in CASES:
    print(f"\n{'=' * 70}\n{label}\n{'=' * 70}")
    result = run_query(payload)
    print(f"  ok:      {result.ok}")
    print(f"  summary: {result.summary()}")
    if result.ok:
        for row in result.rows[:4]:
            print(f"    {row}")
        if result.row_count > 4:
            print(f"    ... {result.row_count - 4} more")
        print(f"  sql returned: {'yes' if result.sql else 'NO — Phase 8 needs it'}")