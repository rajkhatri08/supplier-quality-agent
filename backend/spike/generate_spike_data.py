"""Generate synthetic BIW supplier quality data for the Phase 1 spike.

Throwaway. Not the production schema — see docs/design-decisions.md.
"""

import os
import random
from datetime import date
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

START_YEAR, START_MONTH = 2024, 9   # 24 months ending Aug 2026

# Monthly build volume varies by commodity. Fasteners ship in far larger
# quantities than weld assemblies, so PPM and raw defect count will disagree
# about who is worst — which is what makes the eval questions interesting.
VOLUME_BANDS = {
    "Stampings":       (18_000, 26_000),
    "Weld Assemblies": (9_000, 14_000),
    "Fasteners":       (55_000, 80_000),
    "Sealants":        (30_000, 45_000),
}

# Baseline defect rate per commodity, as PPM. Weld assemblies run hotter than
# fasteners — more process steps, more ways to go wrong.
BASE_PPM = {
    "Stampings":       (280, 420),
    "Weld Assemblies": (300, 460),
    "Fasteners":       (90, 160),
    "Sealants":        (180, 300),
}

# Defect codes available per commodity, so a sealant part never records a
# weld defect.
CODES_BY_COMMODITY = {
    "Stampings":       ["D-STP-01", "D-STP-02", "D-STP-03", "D-STP-04"],
    "Weld Assemblies": ["D-WLD-01", "D-WLD-02", "D-WLD-03", "D-WLD-04"],
    "Fasteners":       ["D-FST-01", "D-FST-02"],
    "Sealants":        ["D-SLR-01", "D-SLR-02"],
}

STATIONS = {
    "Underbody":  ["BIW-Underbody-01", "BIW-Underbody-02"],
    "Side Panel": ["BIW-Framing-01", "BIW-Framing-02"],
    "Roof":       ["BIW-Framing-03", "BIW-Roof-01"],
    "Closures":   ["BIW-Slat-01", "BIW-Slat-02"],
    "Front End":  ["BIW-Docking-01", "BIW-Underbody-03"],
}

# --- planted patterns: see docs/design-decisions.md ---
TREND_SUPPLIER = "SUP-003"
TREND_MULTIPLIERS = [1.25, 1.5, 1.8, 2.1, 2.4, 2.7]

SPIKE_PART = "PN-1042"
SPIKE_MONTH = date(2025, 11, 1)
SPIKE_MULTIPLIER = 8.0

CONCENTRATION_CODE = "D-WLD-01"


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


def month_series(n: int = 24) -> list[date]:
    months = []
    year, month = START_YEAR, START_MONTH
    for _ in range(n):
        months.append(date(year, month, 1))
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return months


def build_production_volume(
    parts: pd.DataFrame, suppliers: pd.DataFrame
) -> pd.DataFrame:
    rng = random.Random(SEED + 1)
    commodity_by_supplier = dict(
        zip(suppliers["supplier_id"], suppliers["commodity"])
    )
    months = month_series()

    rows = []
    for part_id, supplier_id in zip(parts["part_id"], parts["supplier_id"]):
        low, high = VOLUME_BANDS[commodity_by_supplier[supplier_id]]
        baseline = rng.randint(low, high)
        for m in months:
            # +/-12% month-to-month noise around this part's own baseline
            units = int(baseline * rng.uniform(0.88, 1.12))
            rows.append((part_id, m, units))

    return pd.DataFrame(rows, columns=["part_id", "month", "units_produced"])


def build_defects(
    parts: pd.DataFrame,
    suppliers: pd.DataFrame,
    volume: pd.DataFrame,
) -> pd.DataFrame:
    rng = random.Random(SEED + 2)

    commodity_by_supplier = dict(
        zip(suppliers["supplier_id"], suppliers["commodity"])
    )
    part_meta = {
        r.part_id: (r.supplier_id, r.vehicle_system)
        for r in parts.itertuples()
    }
    trend_window = {m: i for i, m in enumerate(month_series()[-6:])}

    rows = []
    for v in volume.itertuples():
        # volume["month"] may come back as date or Timestamp depending on how
        # pandas typed the column. Normalise, or the pattern comparisons below
        # silently never match and no patterns get planted.
        month = pd.Timestamp(v.month).date()

        supplier_id, system = part_meta[v.part_id]
        commodity = commodity_by_supplier[supplier_id]

        low, high = BASE_PPM[commodity]
        ppm = rng.uniform(low, high)

        # Pattern 1 — trend: SUP-003 climbs across the final six months.
        if supplier_id == TREND_SUPPLIER and month in trend_window:
            ppm *= TREND_MULTIPLIERS[trend_window[month]]

        # Pattern 2 — spike: one bad coil, one part, one month.
        if v.part_id == SPIKE_PART and month == SPIKE_MONTH:
            ppm *= SPIKE_MULTIPLIER

        expected = ppm * v.units_produced / 1_000_000
        n_events = rng.randint(
            max(1, int(expected * 0.4)), max(2, int(expected * 0.9))
        )

        codes = CODES_BY_COMMODITY[commodity]
        concentrated = CONCENTRATION_CODE in codes
        if concentrated:
            weights = [
                3.0 if (c == CONCENTRATION_CODE and supplier_id == TREND_SUPPLIER)
                else 0.5 if c == CONCENTRATION_CODE
                else 1.0
                for c in codes
            ]

        for _ in range(n_events):
            # Pattern 3 — concentration: D-WLD-01 favours SUP-003's parts.
            if concentrated:
                code = rng.choices(codes, weights=weights, k=1)[0]
            else:
                code = rng.choice(codes)

            rows.append((
                v.part_id,
                code,
                date(month.year, month.month, rng.randint(1, 28)),
                rng.randint(1, 4),
                rng.choice(STATIONS[system]),
            ))

    return pd.DataFrame(
        rows,
        columns=["part_id", "defect_code", "detected_date", "quantity", "line_station"],
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

    volume = build_production_volume(parts, suppliers)
    volume.to_sql(
        "production_volume", engine, schema="spike",
        if_exists="append", index=False, chunksize=500,
    )
    print(f"production_volume: {len(volume)} rows written")

    defects = build_defects(parts, suppliers, volume)
    defects.to_sql(
        "defects", engine, schema="spike",
        if_exists="append", index=False, chunksize=1000,
    )
    print(f"defects: {len(defects)} rows written")


if __name__ == "__main__":
    main()