"""Generate synthetic BIW supplier quality data for the production schema.

Production code. Seeded and reproducible — the planted patterns are pinned to
specific IDs, so changing the seed or the part-building logic invalidates the
answer key in docs/design-decisions.md.

Carries the fixes the Phase 1 spike identified:
  - sealants have a Critical defect code (D-SLR-03), so Critical-severity
    questions no longer silently exclude an entire commodity
  - low-runner parts build in the hundreds per month, so zero-defect months
    occur naturally and absence is representable

Nothing is written until every row passes its pydantic contract and the three
dataset-level checks pass. A failure leaves the database untouched.
"""

import os
import random
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.contracts import (  # noqa: E402
    Supplier, DefectCode, Part, ProductionVolume, Defect, Report8D,
    check_every_commodity_has_critical,
    check_absence_is_representable,
    check_defects_never_exceed_volume,
)

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

# Low-runner parts: service variants and low-trim components that build in
# the hundreds per month rather than tens of thousands. Two consequences,
# both deliberate:
#   1. At these volumes most months genuinely record zero defects, so
#      absence is representable and "which parts had no defects" is
#      answerable. The Phase 1 spike data could not express this — every
#      part-month had at least one defect event.
#   2. A low-runner with 3 defects on 800 units computes to 3,750 PPM and
#      looks like the worst part in the plant. It is noise. That is a real
#      quality-engineering trap and useful eval material for Phase 6.
LOW_RUNNER_PARTS = {"PN-1006", "PN-1023", "PN-1031", "PN-1044", "PN-1050"}

LOW_RUNNER_VOLUME = (400, 1_400)

COMMODITY_PREFIX = {
    "Stampings": "STP",
    "Weld Assemblies": "WLD",
    "Fasteners": "FST",
    "Sealants": "SLR",
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
# weld defect. A code added to build_defect_codes but not listed here would
# exist in the dimension and never appear in the fact table.
CODES_BY_COMMODITY = {
    "Stampings":       ["D-STP-01", "D-STP-02", "D-STP-03", "D-STP-04"],
    "Weld Assemblies": ["D-WLD-01", "D-WLD-02", "D-WLD-03", "D-WLD-04"],
    "Fasteners":       ["D-FST-01", "D-FST-02", "D-FST-03"],
    "Sealants":        ["D-SLR-01", "D-SLR-02", "D-SLR-03"],
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
    # D-SLR-03 is the Phase 1 fix: without a Critical sealant code, every
    # Critical-severity question silently excluded the whole commodity.
    # A sealer skip on a hem flange is a genuine Critical — it opens a
    # corrosion path into the joint.
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
        ("D-FST-03", "Loose fastener torque",        "Major"),
        ("D-SLR-01", "Sealer bead discontinuity",    "Major"),
        ("D-SLR-02", "Sealer overspray",             "Minor"),
        ("D-SLR-03", "Sealer skip on hem flange",    "Critical"),
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
        if part_id in LOW_RUNNER_PARTS:
            low, high = LOW_RUNNER_VOLUME
        else:
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

        low_ppm, high_ppm = BASE_PPM[commodity]
        ppm = rng.uniform(low_ppm, high_ppm)

        # Pattern 1 — trend: SUP-003 climbs across the final six months.
        if supplier_id == TREND_SUPPLIER and month in trend_window:
            ppm *= TREND_MULTIPLIERS[trend_window[month]]

        # Pattern 2 — spike: one bad coil, one part, one month.
        if v.part_id == SPIKE_PART and month == SPIKE_MONTH:
            ppm *= SPIKE_MULTIPLIER

        expected = ppm * v.units_produced / 1_000_000

        # No floor here. The spike generator used max(1, ...), which
        # guaranteed at least one event per part-month. For a low-runner at
        # a few hundred units, expected falls well below 1 and zero is the
        # normal outcome — which is what makes absence representable.
        low_n = int(expected * 0.4)
        high_n = max(low_n, round(expected * 0.9))
        n_events = rng.randint(low_n, high_n)
        if n_events == 0:
            continue

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


def build_reports_8d() -> pd.DataFrame:
    """Twelve 8D reports, four open.

    The SUP-003 / D-WLD-01 pair is the important one. A closed report from
    early 2025 records the same failure being fixed; an open report from
    mid-2026 records it recurring, which is the electrode-wear trend planted
    in the defect data. Phase 2 decided closed reports rank lower but stay
    retrievable — that pair is what makes the distinction demonstrable, and
    it gives Phase 6 a question that genuinely needs both routes.
    """
    rows = [
        (
            "8D-2025-003", "SUP-003", "D-WLD-01", "PN-1017",
            "Weld porosity on underbody assembly",
            date(2025, 2, 10), date(2025, 5, 22), "Closed",
            "Supplier quality engineer, weld process engineer, line supervisor, "
            "incoming inspection lead.",
            "Porosity found in spot welds on underbody assemblies at incoming "
            "inspection. 41 units affected across three delivery lots.",
            "Affected lots quarantined. 100% visual inspection of incoming "
            "underbody assemblies introduced for four weeks.",
            "Electrode tip wear beyond the dressing interval. Tip dressing was "
            "scheduled by shift count rather than weld count, so high-volume "
            "shifts exceeded the interval before dressing occurred.",
            "Tip dressing rescheduled to a weld-count trigger rather than a "
            "shift-count trigger. Counter installed on the weld controller.",
            "Implemented at supplier on 2025-04-08. Verified over six weeks: "
            "porosity rate returned to baseline.",
            "Weld-count dressing triggers extended to all spot weld cells at "
            "the supplier. Control plan updated.",
            "Closed 2025-05-22 after six weeks of verified conformance. "
            "Effectiveness confirmed by incoming inspection data.",
        ),
        (
            "8D-2026-011", "SUP-003", "D-WLD-01", "PN-1017",
            "Recurring weld porosity — underbody and body side assemblies",
            date(2026, 6, 18), None, "Open",
            "Supplier quality engineer, weld process engineer, supplier plant "
            "manager, customer quality representative.",
            "Weld porosity recurring across multiple part numbers since March "
            "2026. PPM has climbed month over month for five consecutive "
            "months, unlike the single-lot event addressed in 8D-2025-003.",
            "Increased incoming inspection sampling to 20%. Supplier holding "
            "finished stock pending disposition.",
            "Under investigation. Initial evidence points again to electrode "
            "tip wear — the weld-count dressing trigger from 8D-2025-003 "
            "appears not to have been maintained after a controller "
            "replacement in February 2026. Not yet confirmed.",
            "Interim: manual tip dressing at fixed weld counts pending "
            "controller reconfiguration. Permanent action pending root cause "
            "confirmation.",
            "Interim containment active since 2026-06-20. Permanent corrective "
            "action not yet implemented.",
            "Pending. Read-across to other cells commissioned after the "
            "February controller change is planned once root cause is "
            "confirmed.",
            "Open. Target closure after eight weeks of verified conformance "
            "following permanent corrective action.",
        ),
        (
            "8D-2025-007", "SUP-009", "D-STP-01", "PN-1042",
            "Split at draw radius — roof rail variant",
            date(2025, 11, 24), date(2026, 2, 14), "Closed",
            "Press shop engineer, supplier quality engineer, incoming material "
            "inspector, tooling technician.",
            "Splitting at the draw radius on roof rail stampings. 114 units "
            "affected in a single month, well above the historical rate.",
            "Affected lot quarantined and sorted. Coil traceability review "
            "initiated with the steel supplier.",
            "Single coil of base material with elongation below specification. "
            "Coil certificate values were within tolerance but actual material "
            "tested at the low end, insufficient for the draw radius.",
            "Coil rejected and returned. Incoming material testing extended to "
            "include elongation verification on every coil rather than every "
            "batch.",
            "Implemented 2026-01-06. Two subsequent coils tested and released "
            "without incident.",
            "Elongation verification added to the incoming inspection standard "
            "for all deep-drawn stampings.",
            "Closed 2026-02-14. No recurrence in the following six weeks.",
        ),
        (
            "8D-2025-012", "SUP-001", "D-STP-03", None,
            "Dimensional variation on rocker panels",
            date(2025, 6, 3), date(2025, 9, 19), "Closed",
            "Supplier quality engineer, metrology technician, tooling lead.",
            "Rocker panels measuring outside tolerance on two datum points. "
            "Detected at incoming CMM check.",
            "Sorted stock at supplier and at the receiving plant. Temporary "
            "100% CMM check on incoming.",
            "Die wear on the trim station. Die maintenance was interval-based "
            "and the interval had not been revised after a production volume "
            "increase.",
            "Die maintenance interval shortened and tied to stroke count.",
            "Implemented 2025-08-11. Dimensional conformance verified over "
            "five weeks.",
            "Stroke-count maintenance triggers applied to all high-volume dies "
            "at the supplier.",
            "Closed 2025-09-19 after verified conformance.",
        ),
        (
            "8D-2026-004", "SUP-007", "D-SLR-03", None,
            "Sealer skip on hem flange — door assemblies",
            date(2026, 3, 12), None, "Open",
            "Paint shop engineer, sealant supplier representative, quality "
            "engineer.",
            "Intermittent sealer skips on door hem flanges. Skips create a "
            "corrosion path into the joint and are not visible after paint.",
            "Ultrasonic bead verification added at 100% on door assemblies.",
            "Under investigation. Suspected nozzle partial blockage from "
            "material curing at the tip during line stoppages, but not yet "
            "reproduced under controlled conditions.",
            "Interim: nozzle purge cycle added after any stoppage exceeding "
            "ten minutes.",
            "Interim action active since 2026-03-20. Skip rate reduced but "
            "not eliminated.",
            "Pending root cause confirmation.",
            "Open. Investigation ongoing.",
        ),
        (
            "8D-2025-018", "SUP-005", "D-FST-02", None,
            "Missing fasteners on closure hardware kits",
            date(2025, 9, 8), date(2025, 12, 1), "Closed",
            "Supplier quality engineer, packaging engineer, assembly line lead.",
            "Kits delivered with one or more fasteners missing. Detected at "
            "point of use on the assembly line.",
            "Kit-level count verification introduced at incoming.",
            "Counting scale at the supplier's packing station drifting out of "
            "calibration between scheduled checks.",
            "Calibration interval shortened and a daily check-weight "
            "verification added at shift start.",
            "Implemented 2025-10-27. No missing-fastener reports in the "
            "following five weeks.",
            "Daily check-weight verification extended to all kitting stations.",
            "Closed 2025-12-01.",
        ),
        (
            "8D-2026-002", "SUP-004", "D-WLD-03", None,
            "Undersized weld nugget on cowl assemblies",
            date(2026, 1, 20), date(2026, 4, 30), "Closed",
            "Weld process engineer, supplier quality engineer, destructive "
            "test technician.",
            "Undersized nuggets found during routine destructive testing. "
            "Nugget diameter below the minimum specified.",
            "Destructive test frequency increased. Suspect stock held.",
            "Weld current drift following a transformer replacement. The weld "
            "schedule was not re-validated after the change.",
            "Weld schedule re-validated and locked. Change control procedure "
            "updated to require re-validation after any power component "
            "replacement.",
            "Implemented 2026-03-16. Nugget diameters verified conforming over "
            "six weeks of destructive testing.",
            "Change control requirement applied across all weld cells.",
            "Closed 2026-04-30.",
        ),
        (
            "8D-2025-021", "SUP-002", "D-STP-02", None,
            "Surface scoring on visible panels",
            date(2025, 10, 15), date(2026, 1, 8), "Closed",
            "Press shop engineer, quality engineer, tooling technician.",
            "Scoring marks on Class A surfaces. Cosmetic but rejectable on "
            "visible panels.",
            "Affected stock sorted. Visual inspection increased to 100%.",
            "Metal pickup on the die surface from insufficient lubrication at "
            "the draw station.",
            "Lubrication volume increased and application timing adjusted. Die "
            "polishing schedule introduced.",
            "Implemented 2025-12-02. Surface conformance verified over five "
            "weeks.",
            "Lubrication parameters added to the control plan.",
            "Closed 2026-01-08.",
        ),
        (
            "8D-2026-008", "SUP-010", "D-WLD-04", None,
            "Burn-through on thin-gauge body side panels",
            date(2026, 5, 6), None, "Open",
            "Weld process engineer, supplier quality engineer, materials "
            "engineer.",
            "Burn-through on body side panels at the thinnest gauge sections. "
            "Rate increased following a material gauge reduction.",
            "Affected areas reworked. Weld parameters reduced pending "
            "investigation.",
            "Under investigation. Weld schedule was not adjusted for the "
            "reduced material gauge, but the interaction with fit-up gap is "
            "not yet characterised.",
            "Interim: reduced weld current on affected joints. Permanent "
            "action pending characterisation.",
            "Interim active since 2026-05-11.",
            "Pending root cause characterisation.",
            "Open. Design of experiments planned to characterise the current "
            "and fit-up gap interaction.",
        ),
        (
            "8D-2025-014", "SUP-008", "D-SLR-01", None,
            "Sealer bead discontinuity on underbody",
            date(2025, 7, 22), date(2025, 10, 30), "Closed",
            "Paint shop engineer, sealant supplier representative, quality "
            "engineer.",
            "Discontinuous sealer beads on underbody sections. Detected at "
            "visual inspection after application.",
            "100% visual verification of underbody beads introduced.",
            "Material viscosity outside the application window due to storage "
            "below the specified temperature range over a monsoon period.",
            "Heated storage introduced for sealant drums. Viscosity check "
            "added before each batch.",
            "Implemented 2025-09-15. Bead continuity verified over six weeks.",
            "Storage temperature monitoring added with alarm on excursion.",
            "Closed 2025-10-30.",
        ),
        (
            "8D-2026-006", "SUP-006", "D-FST-01", None,
            "Cross-threaded hinge bolts",
            date(2026, 4, 2), date(2026, 7, 15), "Closed",
            "Assembly engineer, supplier quality engineer, tooling technician.",
            "Cross-threading on hinge bolt installation. Detected by torque "
            "monitoring at the station.",
            "Torque monitoring thresholds tightened. Affected assemblies "
            "reworked.",
            "Thread lead-in chamfer below drawing specification on a portion "
            "of supplied bolts, allowing misalignment at start of thread.",
            "Supplier tooling corrected. Chamfer added to incoming inspection "
            "sampling plan.",
            "Implemented 2026-06-01. No cross-threading events in six weeks.",
            "Chamfer dimension added to the supplier control plan.",
            "Closed 2026-07-15.",
        ),
        (
            "8D-2026-013", "SUP-009", "D-STP-04", None,
            "Edge burr on wheel arch stampings",
            date(2026, 7, 28), None, "Open",
            "Press shop engineer, quality engineer, safety representative.",
            "Sharp edge burrs on wheel arch stampings. Handling hazard and "
            "potential sealer damage at assembly.",
            "Deburring operation added as a temporary manual step.",
            "Under investigation. Trim die clearance suspected but not "
            "confirmed; measurement of the die is scheduled.",
            "Interim manual deburring in place. Permanent action pending.",
            "Interim active since 2026-08-03.",
            "Pending die measurement results.",
            "Open. Investigation ongoing.",
        ),
    ]
    df = pd.DataFrame(rows, columns=[
        "report_id", "supplier_id", "defect_code", "part_id", "title",
        "opened_date", "closed_date", "status",
        "d1_team", "d2_problem", "d3_containment", "d4_root_cause",
        "d5_corrective", "d6_implemented", "d7_prevent", "d8_closure",
    ])
    # pandas converts None to nan in object columns. Postgres and pydantic
    # both want None, so convert back explicitly. Caught by the contract on
    # the first run — nan would otherwise have been written to the database.
    return df.astype(object).where(pd.notna(df), None)


def validate(df: pd.DataFrame, model, label: str) -> None:
    """Validate every row against its contract before anything is written.

    Fails on the first bad row with the field named. The database has CHECK
    constraints too, but those fire mid-insert with an opaque message and
    leave a partial write behind.
    """
    for i, row in enumerate(df.to_dict("records")):
        try:
            model(**row)
        except Exception as e:
            raise ValueError(f"{label} row {i} failed validation: {e}") from e
    print(f"  {label}: {len(df)} rows validated")


def main() -> None:
    print("building...")
    suppliers = build_suppliers()
    defect_codes = build_defect_codes()
    parts = build_parts(suppliers)
    volume = build_production_volume(parts, suppliers)
    defects = build_defects(parts, suppliers, volume)
    reports = build_reports_8d()

    print("\nvalidating rows...")
    validate(suppliers, Supplier, "suppliers")
    validate(defect_codes, DefectCode, "defect_codes")
    validate(parts, Part, "parts")
    validate(volume, ProductionVolume, "production_volume")
    validate(defects, Defect, "defects")
    validate(reports, Report8D, "reports_8d")

    # Dataset-level checks. Row validation cannot see these — every
    # individual row can be valid while the dataset as a whole is wrong.
    # The first two caught real problems in the Phase 1 spike data.
    print("\nvalidating dataset...")
    code_models = [DefectCode(**r) for r in defect_codes.to_dict("records")]
    volume_models = [ProductionVolume(**r) for r in volume.to_dict("records")]
    defect_models = [Defect(**r) for r in defects.to_dict("records")]

    check_every_commodity_has_critical(code_models, COMMODITY_PREFIX)
    print("  every commodity has a Critical code")
    check_absence_is_representable(defect_models, volume_models)
    check_defects_never_exceed_volume(defect_models, volume_models)
    print("  defect units never exceed production units")

    # Nothing is written until every check above has passed. A failure
    # leaves the database untouched rather than half-seeded.
    print("\nwriting...")
    for df, table, chunk in [
        (suppliers, "suppliers", None),
        (defect_codes, "defect_codes", None),
        (parts, "parts", None),
        (volume, "production_volume", 500),
        (defects, "defects", 1000),
        (reports, "reports_8d", None),
    ]:
        kwargs = {"chunksize": chunk} if chunk else {}
        df.to_sql(table, engine, schema="public",
                  if_exists="append", index=False, **kwargs)
        print(f"  {table}: {len(df)} rows written")

    print("\ndone")


if __name__ == "__main__":
    main()