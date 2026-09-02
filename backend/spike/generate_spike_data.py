"""Generate synthetic BIW supplier quality data for the Phase 1 spike.

Throwaway. Not the production schema — see docs/design-decisions.md.
"""

import os
import random
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

SEED = 42

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
engine = create_engine(os.environ["DATABASE_URL"])

PART_COUNTS = {
    "SUP-001": 7,
    "SUP-002": 4,
    "SUP-003": 8,
    "SUP-004": 3,
    "SUP-005": 6,
    "SUP-006": 2,
    "SUP-007": 5,
    "SUP-008": 2,
    "SUP-009": 9,
    "SUP-010": 4,
}

# Part name paired with its vehicle system. Pairing is fixed, not random:
# choosing name and system independently produced contradictions such as
# "Underbody Assy" filed under Side Panel.
PART_CATALOG = {
    "Stampings": [
        ("Floor Pan", "Underbody"),
        ("Wheel Arch", "Side Panel"),
        ("Roof Rail", "Roof"),
        ("Rocker Panel", "Side Panel"),
        ("Dash Panel", "Front End"),
    ],
    "Weld Assemblies": [
        ("Body Side Assy", "Side Panel"),
        ("Underbody Assy", "Underbody"),
        ("Cowl Assy", "Front End"),
        ("Rear Rail Assy", "Underbody"),
        ("Front Apron Assy", "Front End"),
    ],
    "Fasteners": [
        ("Hinge Bolt Set", "Closures"),
        ("Door Striker", "Closures"),
        ("Latch Plate", "Closures"),
        ("Bracket Stud", "Underbody"),
        ("Retainer Clip", "Closures"),
    ],
    "Sealants": [
        ("Seam Sealer Bead", "Side Panel"),
        ("Roof Ditch Sealer", "Roof"),
        ("Door Seam Sealer", "Closures"),
        ("Hem Flange Adhesive", "Closures"),
        ("Underbody Sealer", "Underbody"),
    ],
}


def build_suppliers() -> pd.DataFrame:
    rows = [
        ("SUP-001", "Precision Stampings Ltd",   "Stampings",       "Pune"),
        ("SUP-002", "Bharat Metal Forming",      "Stampings",       "Nashik"),
        ("SUP-003", "Unified Weld Assemblies",   "Weld Assemblies", "Pune"),
        ("SUP-004", "Krishna Auto Components",   "Weld Assemblies", "Chennai"),
        ("SUP-005", "Deccan Fasteners",          "Fasteners",       "Hosur"),
        ("SUP-006", "Sterling Fastening Co",     "Fasteners",       "Pune"),
        ("SUP-007", "Adarsh Sealants",           "Sealants",        "Vadodara"),
        ("SUP-008", "Gujarat Polymer Solutions", "Sealants",        "Ahmedabad"),
        ("SUP-009", "Meridian Pressings",        "Stampings",       "Aurangabad"),
        ("SUP-010", "Nova Structural Welding",   "Weld Assemblies", "Jamshedpur"),
    ]
    return pd.DataFrame(
        rows, columns=["supplier_id", "supplier_name", "commodity", "plant_location"]
    )


def build_defect_codes() -> pd.DataFrame:
    rows = [
        ("D-WLD-01", "Weld porosity",                "Critical"),
        ("D-WLD-02", "Weld spatter",                 "Minor"),
        ("D-WLD-03", "Undersized weld nugget",       "Critical"),
        ("D-WLD-04", "Burn-through",                 "Major"),
        ("D-STP-01", "Split at draw radius",         "Critical"),
        ("D-STP-02", "Surface scoring",              "Minor"),
        ("D-STP-03", "Dimensional out-of-tolerance", "Major"),
        ("D-STP-04", "Edge burr",                    "Minor"),
        ("D-FST-01", "Cross-threaded fastener",      "Major"),
        ("D-FST-02", "Missing fastener",             "Critical"),
        ("D-SLR-01", "Sealer bead discontinuity",    "Major"),
        ("D-SLR-02", "Sealer overspray",             "Minor"),
    ]
    return pd.DataFrame(rows, columns=["defect_code", "description", "severity"])


def build_parts(suppliers: pd.DataFrame) -> pd.DataFrame:
    rng = random.Random(SEED)
    commodity_by_supplier = dict(
        zip(suppliers["supplier_id"], suppliers["commodity"])
    )

    rows = []
    part_number = 1001
    for supplier_id, count in PART_COUNTS.items():
        commodity = commodity_by_supplier[supplier_id]
        catalog = PART_CATALOG[commodity]

        order = catalog * ((count // len(catalog)) + 1)
        rng.shuffle(order)

        seen: dict[str, int] = {}
        for name, system in order[:count]:
            seen[name] = seen.get(name, 0) + 1
            display_name = name if seen[name] == 1 else f"{name} Mk{seen[name]}"
            rows.append((f"PN-{part_number}", display_name, supplier_id, system))
            part_number += 1

    return pd.DataFrame(
        rows, columns=["part_id", "part_name", "supplier_id", "vehicle_system"]
    )


def main() -> None:
    suppliers = build_suppliers()
    suppliers.to_sql(
        "suppliers", engine, schema="spike", if_exists="append", index=False
    )
    print(f"suppliers: {len(suppliers)} rows written")

    defect_codes = build_defect_codes()
    defect_codes.to_sql(
        "defect_codes", engine, schema="spike", if_exists="append", index=False
    )
    print(f"defect_codes: {len(defect_codes)} rows written")

    parts = build_parts(suppliers)
    parts.to_sql(
        "parts", engine, schema="spike", if_exists="append", index=False
    )
    print(f"parts: {len(parts)} rows written")


if __name__ == "__main__":
    main()