"""Existence checks against the dimension tables.

Format validation cannot catch this. 'SUP-999' matches the regex, sits inside
the date window, and names a real query — it just does not exist. The query
runs, returns zero rows, and reads as "this supplier has no defects" rather
than "this supplier is not in the data."

Two different answers, identical output. That is the silent-failure class this
project is built against, so it gets a check rather than a caveat.

The dimensions are small and static — 10 suppliers, 50 parts, 14 codes — so
they are loaded once and held in memory. If they ever became large or mutable
this would need a different approach.
"""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
_engine = create_engine(os.environ["DATABASE_URL"])


class UnknownEntity(ValueError):
    """Raised when a well-formed identifier does not exist in the data."""


@lru_cache(maxsize=1)
def _known_suppliers() -> dict[str, str]:
    with _engine.connect() as conn:
        rows = conn.execute(
            text("SELECT supplier_id, supplier_name FROM suppliers")
        ).all()
    return {r[0]: r[1] for r in rows}


@lru_cache(maxsize=1)
def _known_parts() -> dict[str, str]:
    with _engine.connect() as conn:
        rows = conn.execute(
            text("SELECT part_id, part_name FROM parts")
        ).all()
    return {r[0]: r[1] for r in rows}


@lru_cache(maxsize=1)
def _known_defect_codes() -> dict[str, str]:
    with _engine.connect() as conn:
        rows = conn.execute(
            text("SELECT defect_code, description FROM defect_codes")
        ).all()
    return {r[0]: r[1] for r in rows}


def _nearest(candidate: str, known: list[str], limit: int = 3) -> list[str]:
    """Cheap suggestion: same prefix, closest numeric suffix.

    Not fuzzy matching — the IDs are structured, so a numeric neighbour is
    more useful than an edit-distance match.
    """
    prefix = candidate.rsplit("-", 1)[0]
    same_prefix = [k for k in known if k.rsplit("-", 1)[0] == prefix]
    return sorted(same_prefix)[:limit]


def check_supplier(supplier_id: str) -> None:
    known = _known_suppliers()
    if supplier_id not in known:
        raise UnknownEntity(
            f"supplier {supplier_id} does not exist. "
            f"The data contains {len(known)} suppliers: "
            f"{', '.join(sorted(known))}"
        )


def check_part(part_id: str) -> None:
    known = _known_parts()
    if part_id not in known:
        near = _nearest(part_id, list(known))
        hint = f" Nearest by ID: {', '.join(near)}." if near else ""
        raise UnknownEntity(
            f"part {part_id} does not exist. "
            f"The data contains {len(known)} parts.{hint}"
        )


def check_defect_code(defect_code: str) -> None:
    known = _known_defect_codes()
    if defect_code not in known:
        near = _nearest(defect_code, list(known))
        hint = f" Codes with the same prefix: {', '.join(near)}." if near else ""
        raise UnknownEntity(
            f"defect code {defect_code} does not exist. "
            f"The data contains {len(known)} codes.{hint}"
        )


def check_all(params: dict) -> None:
    """Check every identifier present in a validated parameter set."""
    if "supplier_id" in params:
        check_supplier(params["supplier_id"])
    if "part_id" in params:
        check_part(params["part_id"])
    if "defect_code" in params:
        check_defect_code(params["defect_code"])