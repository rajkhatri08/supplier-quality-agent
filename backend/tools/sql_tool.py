"""The SQL tool.

Takes a JSON payload from the agent, returns a structured result. Never
raises — every failure is a reason the agent can read and report.

Pipeline:
    1. Validate format         pydantic, query_params
    2. Check existence         dimension tables, existence
    3. Look up the query       query_catalogue
    4. Execute                 bound parameters, read-only connection
    5. Return rows + the SQL that ran

The SQL comes back with the result because Phase 8 has to show it. An agent
that reports a number without being able to show where it came from fails the
depth bar the whole project is aimed at.

Failure is structured rather than raised. Four instances of DNS failure during
development took down the entire request with an OperationalError — in a
deployed agent that is a stack trace where an explanation should be.
"""

import os
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.existence import UnknownEntity, check_all  # noqa: E402
from tools.query_catalogue import CATALOGUE  # noqa: E402
from tools.query_params import parse_query_call  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
_engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)

FailureKind = Literal[
    "invalid_request",   # malformed payload or unknown query
    "unknown_entity",    # well-formed identifier that does not exist
    "unavailable",       # database unreachable
    "query_failed",      # SQL ran and errored
]


@dataclass
class SqlResult:
    ok: bool
    query_id: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    sql: str | None = None
    rows: list[dict] = field(default_factory=list)
    row_count: int = 0
    failure_kind: FailureKind | None = None
    reason: str | None = None

    def summary(self) -> str:
        """One line the agent can put in front of a user."""
        if self.ok:
            return f"{self.query_id} returned {self.row_count} rows"
        return f"{self.failure_kind}: {self.reason}"


def _serialise(value: Any) -> Any:
    """Dates and Decimals do not survive JSON. Convert at the boundary."""
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "quantize"):        # Decimal
        return float(value)
    return value


def _readable(e: ValidationError) -> str:
    """Turn a pydantic error into something an agent can act on.

    Pydantic puts the model name on line 1 and the actual problem on the
    lines below. Taking only the first line loses every detail and makes
    three different failures look identical — a decline that says nothing
    is barely better than a silent failure.
    """
    return "; ".join(
        f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
        for err in e.errors()
    )


def run_query(payload: dict) -> SqlResult:
    """Validate, check, execute. Returns a result; never raises."""

    # 1. Format
    try:
        call = parse_query_call(payload)
    except ValidationError as e:
        return SqlResult(
            ok=False,
            query_id=payload.get("query_id"),
            failure_kind="invalid_request",
            reason=_readable(e),
        )
    except Exception as e:
        return SqlResult(
            ok=False,
            query_id=payload.get("query_id"),
            failure_kind="invalid_request",
            reason=str(e).split("\n")[0],
        )

    params = call.model_dump(exclude={"query_id"})

    # 2. Existence. A connection failure here is 'unavailable', not
    #    'unknown_entity' — the identifier may be perfectly valid.
    try:
        check_all(params)
    except UnknownEntity as e:
        return SqlResult(
            ok=False, query_id=call.query_id, params=params,
            failure_kind="unknown_entity", reason=str(e),
        )
    except SQLAlchemyError as e:
        return SqlResult(
            ok=False, query_id=call.query_id, params=params,
            failure_kind="unavailable",
            reason=f"could not verify identifiers: {type(e).__name__}",
        )

    # 3. Look up
    entry = CATALOGUE[call.query_id]

    # 4. Execute. connect() never commits, so nothing here can write.
    try:
        with _engine.connect() as conn:
            result = conn.execute(text(entry.sql), params)
            columns = list(result.keys())
            rows = [
                {c: _serialise(v) for c, v in zip(columns, row)}
                for row in result.fetchall()
            ]
    except SQLAlchemyError as e:
        kind: FailureKind = (
            "unavailable" if "OperationalError" in type(e).__name__
            else "query_failed"
        )
        return SqlResult(
            ok=False, query_id=call.query_id, params=params,
            sql=entry.sql.strip(), failure_kind=kind,
            reason=f"{type(e).__name__}: {str(e).split(chr(10))[0][:160]}",
        )

    # 5. Return rows with the SQL that produced them
    return SqlResult(
        ok=True,
        query_id=call.query_id,
        params=params,
        sql=entry.sql.strip(),
        rows=rows,
        row_count=len(rows),
    )


def catalogue_manifest() -> list[dict]:
    """What the agent sees when choosing a query.

    Descriptions and parameter names only — never the SQL. The agent selects
    from a fixed set; it does not need to see, and cannot influence, the
    statement that runs.
    """
    return [
        {"query_id": e.query_id, "description": e.description,
         "params": list(e.params)}
        for e in CATALOGUE.values()
    ]