"""Structured trace of an agent run.

One record per question: what was asked, where it routed, why, what each tool
returned, and how long it took. Phase 8 renders this; nothing else needs to
be assembled at display time.

Written as a fixed shape rather than free-text logging because the trace is a
deliverable, not a debugging aid. The interview criterion is depth of
understanding, and a routing decision nobody can inspect fails it — a number
with no visible provenance is exactly the failure this project is built
against.

Every field is populated even when a tool declines. A failed tool call is
part of the trace, not an absence from it.
"""

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ToolTrace:
    """One tool invocation."""
    tool: str                       # 'sql' | 'documents'
    ok: bool
    latency_ms: int
    query_id: str | None = None     # SQL: which catalogue query
    params: dict[str, Any] = field(default_factory=dict)
    sql: str | None = None          # the statement that actually ran
    row_count: int | None = None
    open_count: int | None = None   # documents: passages from open reports
    closed_count: int | None = None # documents: passages from closed reports
    citations: list[str] = field(default_factory=list)
    failure_kind: str | None = None
    reason: str | None = None


@dataclass
class RunTrace:
    """One question, start to finish."""
    question: str
    timestamp: str
    route: str | None
    routing_reason: str
    routing_latency_ms: int
    tools: list[ToolTrace] = field(default_factory=list)
    total_latency_ms: int = 0
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def summary(self) -> str:
        """One line for a terminal or a log aggregator."""
        parts = [f"route={self.route}"]
        for t in self.tools:
            if t.ok:
                if t.tool == "sql":
                    parts.append(f"sql:{t.query_id}({t.row_count} rows)")
                else:
                    parts.append(
                        f"docs:{t.open_count}open/{t.closed_count}closed"
                    )
            else:
                parts.append(f"{t.tool}:{t.failure_kind}")
        parts.append(f"{self.total_latency_ms}ms")
        return " ".join(parts)


class Timer:
    """Wall-clock milliseconds. Latency belongs in the trace because a
    routing decision that takes eight seconds is a different product from one
    that takes eight hundred milliseconds, and only measurement says which
    this is."""

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.ms = int((time.perf_counter() - self._start) * 1000)
        return False


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")