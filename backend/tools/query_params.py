"""Parameter models for the query catalogue.

The LLM never writes SQL. It returns JSON naming one query from a fixed set
plus that query's parameters. This module validates that JSON before anything
reaches the database.

Two layers, doing different jobs:

  Format   — pydantic. Wrong type, malformed ID, date outside the data
             window, unknown query name: rejected here.
  Existence — checked against the dimension tables. 'SUP-999' passes every
             regex and does not exist. Without this check it returns zero
             rows and looks like a real answer, which is the silent-failure
             class this project exists to avoid.

Injection is already structurally closed by the catalogue: parameters bind
through the driver rather than being interpolated into SQL text, so a
malicious value is a string that matches nothing. What this module adds is
loud failure instead of quiet emptiness.
"""

from datetime import date
from typing import Literal, Union

from pydantic import BaseModel, Field, model_validator

WINDOW_START = date(2024, 9, 1)
WINDOW_END = date(2026, 8, 31)

SUPPLIER_ID = Field(pattern=r"^SUP-\d{3}$")
PART_ID = Field(pattern=r"^PN-\d{4}$")
DEFECT_CODE = Field(pattern=r"^D-[A-Z]{3}-\d{2}$")


class _WindowMixin(BaseModel):
    @model_validator(mode="after")
    def window_is_sane(self):
        start = getattr(self, "start_month", None) or getattr(self, "start_date")
        end = getattr(self, "end_month", None) or getattr(self, "end_date")
        if start > end:
            raise ValueError(f"start {start} is after end {end}")
        if end < WINDOW_START or start > WINDOW_END:
            raise ValueError(
                f"range {start}..{end} lies entirely outside the data window "
                f"({WINDOW_START} to {WINDOW_END})"
            )
        return self


class _MonthMixin(_WindowMixin):
    @model_validator(mode="after")
    def months_are_first_of_month(self):
        for name in ("start_month", "end_month"):
            value = getattr(self, name)
            if value.day != 1:
                raise ValueError(
                    f"{name} must be the first of a month, got {value}. "
                    f"production_volume is keyed by month."
                )
        return self


class SupplierPpmOverWindow(_MonthMixin):
    query_id: Literal["supplier_ppm_over_window"]
    supplier_id: str = SUPPLIER_ID
    start_month: date
    end_month: date


class SupplierPpmByMonth(_MonthMixin):
    query_id: Literal["supplier_ppm_by_month"]
    supplier_id: str = SUPPLIER_ID
    start_month: date
    end_month: date


class SupplierPpmRanking(_MonthMixin):
    query_id: Literal["supplier_ppm_ranking"]
    start_month: date
    end_month: date


class PartPpmRanking(_MonthMixin):
    query_id: Literal["part_ppm_ranking"]
    start_month: date
    end_month: date


class PartsWithoutDefects(_MonthMixin):
    query_id: Literal["parts_without_defects"]
    start_month: date
    end_month: date


class DefectCodeBreakdown(_WindowMixin):
    query_id: Literal["defect_code_breakdown"]
    supplier_id: str = SUPPLIER_ID
    start_date: date
    end_date: date


class SeverityBreakdown(_WindowMixin):
    query_id: Literal["severity_breakdown"]
    supplier_id: str = SUPPLIER_ID
    start_date: date
    end_date: date


class DefectCodeBySupplier(_WindowMixin):
    query_id: Literal["defect_code_by_supplier"]
    defect_code: str = DEFECT_CODE
    start_date: date
    end_date: date


# Discriminated union: pydantic picks the model by query_id, so an unknown
# query name fails here rather than reaching the catalogue lookup.
QueryCall = Union[
    SupplierPpmOverWindow,
    SupplierPpmByMonth,
    SupplierPpmRanking,
    PartPpmRanking,
    PartsWithoutDefects,
    DefectCodeBreakdown,
    SeverityBreakdown,
    DefectCodeBySupplier,
]

MODEL_BY_QUERY_ID = {
    "supplier_ppm_over_window": SupplierPpmOverWindow,
    "supplier_ppm_by_month": SupplierPpmByMonth,
    "supplier_ppm_ranking": SupplierPpmRanking,
    "part_ppm_ranking": PartPpmRanking,
    "parts_without_defects": PartsWithoutDefects,
    "defect_code_breakdown": DefectCodeBreakdown,
    "severity_breakdown": SeverityBreakdown,
    "defect_code_by_supplier": DefectCodeBySupplier,
}


def parse_query_call(payload: dict) -> QueryCall:
    """Validate a raw JSON payload from the LLM.

    Raises ValueError with a readable message on anything malformed.
    """
    query_id = payload.get("query_id")
    if query_id not in MODEL_BY_QUERY_ID:
        known = ", ".join(sorted(MODEL_BY_QUERY_ID))
        raise ValueError(
            f"unknown query_id {query_id!r}. Available queries: {known}"
        )
    return MODEL_BY_QUERY_ID[query_id](**payload)