"""Generate synthetic BIW supplier quality data for the Phase 1 spike.

Throwaway. Not the production schema — see docs/design-decisions.md.
"""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

SEED = 42

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
engine = create_engine(os.environ["DATABASE_URL"])


def build_suppliers() -> pd.DataFrame:
    rows = [
        ("SUP-001", "Precision Stampings Ltd",   "Stampings",       "Pune"),
        ("SUP-002", "Bharat Metal Forming",      "Stampings",       "Nashik"),
        ("SUP-003", "Unified Weld Assemblies",   "Weld Assemblies", "Pune"),
        ("SUP-004", "Krishna Auto Components",   "Weld Assemblies", "Chennai"),
        ("SUP-005", "Deccan Fasteners",          "Fasteners",       "Hosur"),
        ("SUP-006", "Sterling Fastening Co",     "Fasteners",       "Pune"),
        ("SUP-007", "Adarsh Sealants",           "Sealants",        "Vadodara"),
        ("SUP-008", "Gujarat Polymer Solutions",  "Sealants",       "Ahmedabad"),
        ("SUP-009", "Meridian Pressings",        "Stampings",       "Aurangabad"),
        ("SUP-010", "Nova Structural Welding",   "Weld Assemblies", "Jamshedpur"),
    ]
    return pd.DataFrame(
        rows, columns=["supplier_id", "supplier_name", "commodity", "plant_location"]
    )


def main() -> None:
    suppliers = build_suppliers()
    suppliers.to_sql(
        "suppliers", engine, schema="spike", if_exists="append", index=False
    )
    print(f"suppliers: {len(suppliers)} rows written")


if __name__ == "__main__":
    main()
