"""Run one question end to end: route, call tools, return a trace.

This is the whole agent. Everything it does is recorded in the trace it
returns; there is no path where a result reaches a user without its
provenance attached.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.router import route as choose_route  # noqa: E402
from agent.trace import RunTrace, Timer, ToolTrace, now  # noqa: E402
from tools.document_tool import search  # noqa: E402
from tools.sql_tool import run_query  # noqa: E402


def _run_sql(query_id: str | None, params: dict) -> ToolTrace:
    if not query_id:
        return ToolTrace(
            tool="sql", ok=False, latency_ms=0,
            failure_kind="invalid_request",
            reason="the router chose SQL but named no query",
        )

    payload = {"query_id": query_id, **params}
    with Timer() as t:
        result = run_query(payload)

    return ToolTrace(
        tool="sql",
        ok=result.ok,
        latency_ms=t.ms,
        query_id=result.query_id,
        params=result.params,
        sql=result.sql,
        row_count=result.row_count if result.ok else None,
        # Capped. Every catalogue query returns 50 rows or fewer, so nothing
        # is truncated today — the cap is there so a future query returning
        # thousands cannot make the trace unusable.
        rows=result.rows[:50] if result.ok else [],
        failure_kind=result.failure_kind,
        reason=result.reason,
    )


def _run_docs(question: str, supplier_id: str | None = None) -> ToolTrace:
    """Retrieve passages, filtered by supplier when the question names one.

    Filtering matters. Without it, "why is SUP-003's defect rate getting
    worse" returned five of six passages from 8D-2026-009 — the SUP-001
    gauge-drift report. Semantically similar (a PPM rise, a root cause),
    wrong supplier. The trace caught it; the passage counts alone looked fine.

    The trade is real: a filter that hides a relevant report from another
    supplier turns a false positive into a false negative. Accepted because
    a question naming a supplier is usually about that supplier.
    """
    with Timer() as t:
        result = search(question, supplier_id=supplier_id)

    if not result.ok:
        return ToolTrace(
            tool="documents", ok=False, latency_ms=t.ms,
            failure_kind=result.failure_kind, reason=result.reason,
        )

    ordered = result.open_passages + result.closed_passages

    return ToolTrace(
        tool="documents",
        ok=True,
        latency_ms=t.ms,
        open_count=len(result.open_passages),
        closed_count=len(result.closed_passages),
        citations=[p.citation() for p in ordered],
        # Full passage text with status and distance. Ordered open-first per
        # the Phase 2 decision. The distance is included so a viewer can see
        # how close a match actually was rather than trusting that it was
        # returned at all.
        passages=[
            {
                "citation": p.citation(),
                "text": p.text,
                "distance": p.distance,
                "status": p.status,
                "report_id": p.report_id,
                "discipline": p.discipline_title,
            }
            for p in ordered
        ],
    )


def run(question: str, sql_params: dict | None = None) -> RunTrace:
    """Route the question and call whichever tools the route names.

    sql_params is supplied by the caller for now. Extracting parameters from
    the question is a separate concern from routing, and mixing them would
    make a routing failure and an extraction failure look the same in the
    trace.
    """
    with Timer() as total:
        with Timer() as routing:
            decision = choose_route(question)

        trace = RunTrace(
            question=question,
            timestamp=now(),
            route=decision.route,
            routing_reason=decision.reason,
            routing_latency_ms=routing.ms,
            error=decision.error,
        )

        if not decision.error:
            params = dict(sql_params or {})
            if decision.supplier_id and "supplier_id" not in params:
                params["supplier_id"] = decision.supplier_id

            if decision.route in ("SQL", "BOTH"):
                trace.tools.append(_run_sql(decision.query_id, params))

            if decision.route in ("DOCS", "BOTH"):
                trace.tools.append(
                    _run_docs(question, decision.supplier_id)
                )

            # NEITHER calls no tools. That is the correct behaviour, and the
            # empty tools list is the evidence — not an omission.

    trace.total_latency_ms = total.ms
    return trace


if __name__ == "__main__":
    examples = [
        ("Why is SUP-003's defect rate getting worse?",
         {"start_month": "2026-03-01", "end_month": "2026-08-01"}),
        ("What is SUP-003's on-time delivery rate?", {}),
        ("What was the root cause of the roof rail splitting?", {}),
    ]

    for question, params in examples:
        print(f"\n{'=' * 74}\n{question}\n{'=' * 74}")
        trace = run(question, params)
        print(f"  {trace.summary()}")
        print(f"  routing reason: {trace.routing_reason}")
        for t in trace.tools:
            if t.ok and t.tool == "sql":
                print(f"  sql ran in {t.latency_ms}ms, {t.row_count} rows")
                for row in t.rows[:3]:
                    print(f"    {row}")
            elif t.ok:
                print(f"  docs in {t.latency_ms}ms: "
                      f"{t.open_count} open, {t.closed_count} closed")
                for p in t.passages[:3]:
                    print(f"    {p['distance']:.4f}  {p['citation']}")
            else:
                print(f"  {t.tool} declined: {t.failure_kind} — {t.reason}")