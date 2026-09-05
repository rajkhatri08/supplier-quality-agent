"""Data contract for generated data.

Every row is validated before it reaches Postgres. The database has CHECK
constraints too, but they fire one row at a time with an opaque message.
These fail early with a readable error naming the field and the row.

Phase 1 found two properties the spike data could not express. Both are
enforced here as requirements rather than left to chance:
  - zero-defect part-months must be possible (absence must be representable)
  - every commodity must have at least one Critical defect code
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

COMMODITIES = Literal["Stampings", "Weld Assemblies", "Fasteners", "Sealants"]
SYSTEMS = Literal["Underbody", "Side Panel", "Roof", "Closures", "Front End"]
SEVERITIES = Literal["Critical", "Major", "Minor"]

WINDOW_START = date(2024, 9, 1)
WINDOW_END = date(2026, 8, 31)


class Supplier(BaseModel):
    supplier_id: str = Field(pattern=r"^SUP-\d{3}$")
    supplier_name: str = Field(min_length=3)
    commodity: COMMODITIES
    plant_location: str = Field(min_length=2)


class DefectCode(BaseModel):
    defect_code: str = Field(pattern=r"^D-[A-Z]{3}-\d{2}$")
    description: str = Field(min_length=3)
    severity: SEVERITIES


class Part(BaseModel):
    part_id: str = Field(pattern=r"^PN-\d{4}$")
    part_name: str = Field(min_length=3)
    supplier_id: str = Field(pattern=r"^SUP-\d{3}$")
    vehicle_system: SYSTEMS


class ProductionVolume(BaseModel):
    part_id: str = Field(pattern=r"^PN-\d{4}$")
    month: date
    units_produced: int = Field(gt=0)

    @model_validator(mode="after")
    def month_in_window_and_first_of_month(self):
        if self.month.day != 1:
            raise ValueError(f"month must be the 1st, got {self.month}")
        if not (WINDOW_START <= self.month <= WINDOW_END):
            raise ValueError(f"month {self.month} outside window")
        return self


class Defect(BaseModel):
    part_id: str = Field(pattern=r"^PN-\d{4}$")
    defect_code: str = Field(pattern=r"^D-[A-Z]{3}-\d{2}$")
    detected_date: date
    quantity: int = Field(gt=0)
    line_station: str = Field(min_length=3)

    @model_validator(mode="after")
    def date_in_window(self):
        if not (WINDOW_START <= self.detected_date <= WINDOW_END):
            raise ValueError(f"detected_date {self.detected_date} outside window")
        return self


class Report8D(BaseModel):
    report_id: str = Field(pattern=r"^8D-\d{4}-\d{3}$")
    supplier_id: str = Field(pattern=r"^SUP-\d{3}$")
    defect_code: str = Field(pattern=r"^D-[A-Z]{3}-\d{2}$")
    part_id: str | None = None
    title: str = Field(min_length=5)
    opened_date: date
    closed_date: date | None = None
    status: Literal["Open", "Closed"]
    d1_team: str = Field(min_length=10)
    d2_problem: str = Field(min_length=10)
    d3_containment: str = Field(min_length=10)
    d4_root_cause: str = Field(min_length=10)
    d5_corrective: str = Field(min_length=10)
    d6_implemented: str = Field(min_length=10)
    d7_prevent: str = Field(min_length=10)
    d8_closure: str = Field(min_length=10)

    @model_validator(mode="after")
    def status_matches_closed_date(self):
        if self.status == "Open" and self.closed_date is not None:
            raise ValueError(f"{self.report_id}: Open but has closed_date")
        if self.status == "Closed" and self.closed_date is None:
            raise ValueError(f"{self.report_id}: Closed but no closed_date")
        if self.closed_date and self.closed_date < self.opened_date:
            raise ValueError(f"{self.report_id}: closed before opened")
        return self


# --- dataset-level checks -------------------------------------------------
# Row validation cannot see these. They are properties of the whole dataset,
# and Phase 1 showed both fail silently when unchecked.

def check_every_commodity_has_critical(
    codes: list[DefectCode], commodity_prefix: dict[str, str]
) -> None:
    """Phase 1 finding 2: sealants had no Critical code, so every
    Critical-severity question silently excluded an entire commodity."""
    critical_prefixes = {
        c.defect_code.split("-")[1] for c in codes if c.severity == "Critical"
    }
    for commodity, prefix in commodity_prefix.items():
        if prefix not in critical_prefixes:
            raise ValueError(
                f"{commodity} (prefix {prefix}) has no Critical defect code"
            )


def check_absence_is_representable(
    defects: list[Defect], volume: list[ProductionVolume]
) -> None:
    """Phase 1 finding 1: every part-month had at least one defect event, so
    no 'which X had no Y' question was answerable."""
    with_defects = {(d.part_id, d.detected_date.replace(day=1)) for d in defects}
    all_months = {(v.part_id, v.month) for v in volume}
    empty = all_months - with_defects
    if not empty:
        raise ValueError(
            "no defect-free part-months exist — absence is not representable"
        )
    print(f"  absence check: {len(empty)} of {len(all_months)} part-months "
          f"are defect-free")


def check_defects_never_exceed_volume(
    defects: list[Defect], volume: list[ProductionVolume]
) -> None:
    """A part-month cannot have more defective units than units produced.
    Violating this gives PPM above 1,000,000."""
    produced = {(v.part_id, v.month): v.units_produced for v in volume}
    totals: dict[tuple[str, date], int] = {}
    for d in defects:
        key = (d.part_id, d.detected_date.replace(day=1))
        totals[key] = totals.get(key, 0) + d.quantity
    for key, total in totals.items():
        if key not in produced:
            raise ValueError(f"{key}: defects with no production volume")
        if total > produced[key]:
            raise ValueError(
                f"{key}: {total} defect units > {produced[key]} produced"
            )