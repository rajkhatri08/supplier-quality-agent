"""HTTP layer.

Two endpoints rather than one, deliberately. The routing decision is
available several seconds before the tools finish, and it is the most
interesting thing the agent produces — the route and the reason are what the
demo is about. Returning them immediately lets the UI show the decision while
the tools are still running.

Two plain endpoints rather than server-sent events: same effect for the user,
one less protocol to deploy and explain.
"""

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent.router import route as choose_route  # noqa: E402
from agent.run import _run_docs, _run_sql  # noqa: E402
from agent.trace import Timer, now  # noqa: E402
from tools.sql_tool import catalogue_manifest  # noqa: E402

app = FastAPI(title="Supplier Quality Risk Agent")

# Vercel serves the frontend from a different origin, so the browser needs
# permission to call this. Tightened to the deployed origin in Phase 9;
# wide open here because the frontend runs on localhost during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class ToolRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    route: str
    query_id: str | None = None
    supplier_id: str | None = None
    sql_params: dict = Field(default_factory=dict)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "timestamp": now()}


@app.get("/catalogue")
def catalogue() -> list[dict]:
    """What the router can choose from. Descriptions and parameter names —
    never SQL. The UI shows this so a viewer can see the agent is selecting
    from a fixed set rather than writing queries."""
    return catalogue_manifest()


@app.post("/route")
def route_question(body: Question) -> dict:
    """Step one: the routing decision, returned as soon as it exists."""
    with Timer() as t:
        decision = choose_route(body.question)

    return {
        "question": body.question,
        "route": decision.route,
        "reason": decision.reason,
        "query_id": decision.query_id,
        "supplier_id": decision.supplier_id,
        "latency_ms": t.ms,
        "error": decision.error,
    }


@app.post("/tools")
def run_tools(body: ToolRequest) -> dict:
    """Step two: run whichever tools the route names.

    The caller passes back the routing decision rather than the server
    holding session state. Two requests, no session, no cleanup — and the
    decision the UI acted on is visibly the one it was given.
    """
    tools = []

    with Timer() as total:
        if body.route in ("SQL", "BOTH"):
            # The router extracts supplier_id as a routing field, but the SQL
            # tool expects it as a query parameter. Merge it in rather than
            # making the caller send it twice — it reached retrieval and not
            # SQL on the first run, and pydantic caught it as a missing field.
            params = dict(body.sql_params)
            if body.supplier_id and "supplier_id" not in params:
                params["supplier_id"] = body.supplier_id
            tools.append(_run_sql(body.query_id, params))

        if body.route in ("DOCS", "BOTH"):
            tools.append(_run_docs(body.question, body.supplier_id))

    return {
        "question": body.question,
        "route": body.route,
        "tools": [t.__dict__ for t in tools],
        "latency_ms": total.ms,
    }