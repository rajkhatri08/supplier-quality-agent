"""The router.

Chooses between the SQL tool, the document tool, both, or neither — states
why, and extracts the supplier when the question names one. The reason is not
decoration: Phase 8 shows it, and a routing decision nobody can explain fails
the depth bar this project is aimed at.

The model sees the query catalogue's descriptions, a summary of what the
documents contain, and the list of suppliers that exist. It does not see SQL,
and it does not write SQL: it names a route and, for SQL routes, names a
query from the fixed catalogue.

Change log, measured against eval/routing-set.json:

  baseline  18/24 (75%), BOTH 1/6.
            Five of six BOTH questions went to DOCS, each with a true reason
            — the explanation does live in the reports. The prompt described
            what a SQL-only answer would be missing ("its reason") but had no
            equivalent for what a DOCS-only answer would be missing.

  change 1  21/24 (87.5%), BOTH 4/6, SQL 7/7, DOCS 6/6.
            BOTH criterion made bidirectional. Nothing else dropped. But N03
            regressed from a quiet miss to a confident one: it routed SUP-011
            to BOTH and claimed SQL held PPM data confirming a spike. There
            is no SUP-011.

  change 2  21-22/24 across four runs. NEITHER 5/5 — N03 fixed by putting the
            supplier list in the prompt. Three questions (R05, BOTH04,
            BOTH05) flip between runs; they sit on boundaries the rule draws
            ambiguously. Reported as a range rather than a single number.

  change 3  supplier_id extracted alongside the route, so retrieval can be
            filtered. Not a routing-accuracy change — a retrieval-quality one.
"""

import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from google import genai

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.existence import _known_suppliers  # noqa: E402
from tools.sql_tool import catalogue_manifest  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

MODEL = "gemini-3.6-flash"

Route = Literal["SQL", "DOCS", "BOTH", "NEITHER"]

DOCUMENT_SUMMARY = """The document store holds 13 8D corrective action \
reports covering supplier quality problems from 2025 and 2026. Four are open \
and nine are closed. Each report has eight disciplines: team, problem \
description, interim containment, root cause, permanent corrective action, \
implementation, prevention, and closure.

They record why a problem happened, what was done about it, whether it is \
resolved, and whether a problem has occurred before. They do not contain \
production figures, defect counts or rates."""

PROMPT = """You route questions about supplier quality data to the right \
source.

TWO SOURCES ARE AVAILABLE.

1. SQL — a database of defect records and production volumes. Available
   queries:
{catalogue}

2. DOCUMENTS — 8D corrective action reports.
{documents}

The data covers exactly these suppliers: {suppliers}
A question about any other supplier is NEITHER — the data does not contain
it, and neither source can say anything about it.

CHOOSE ONE ROUTE:

SQL      — the answer is a number, a ranking, or a set of records.
DOCS     — the answer is an explanation, a cause, an action taken, or a status
           recorded in a report.
BOTH     — neither source alone gives a complete answer. Check both
           directions before choosing a single source:
             - would a SQL-only answer be a number with no explanation?
             - would a DOCS-only answer be an explanation with no evidence
               that the thing described is actually happening, or a claim
               about a number that the answer never shows?
           If either is true, choose BOTH. If neither is, choose the single
           source that holds the answer. Both sources having something to say
           is not enough.
NEITHER  — the data needed does not exist, or the question refers to something
           that is not in the data.

If a question is ambiguous about which metric is meant — defect events versus
defect units, rate versus count — that is not a reason to choose BOTH. Choose
the source that holds the answer and state which interpretation you would use.

If the question names a supplier, return its ID. Retrieval is filtered by it,
so a question about SUP-003 does not surface reports about other suppliers.

QUESTION: {question}

Reply with JSON and nothing else:
{{"route": "SQL|DOCS|BOTH|NEITHER", "reason": "one sentence", \
"query_id": "catalogue query id, or null", \
"supplier_id": "SUP-0NN if the question names one, else null"}}"""


@dataclass
class RoutingDecision:
    question: str
    route: Route | None
    reason: str
    query_id: str | None
    raw: str
    supplier_id: str | None = None
    error: str | None = None


def _format_catalogue() -> str:
    return "\n".join(
        f"   - {e['query_id']}: {e['description']}"
        for e in catalogue_manifest()
    )


def _known_entities() -> str:
    """The router cannot decline a question about a supplier that does not
    exist unless it knows which suppliers do. Ten IDs, static, already loaded
    by the existence check.

    Baseline routed SUP-011 to DOCS — a quiet miss. After change 1 it routed
    to BOTH and claimed SQL held PPM data confirming a spike for SUP-011.
    A confident claim about data that does not exist is worse than a silent
    miss, so the fix belongs in the router rather than only in the tool.
    """
    return ", ".join(sorted(_known_suppliers()))


def _strip_fences(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()


def route(question: str) -> RoutingDecision:
    """Ask the model to choose a route. Never raises."""
    prompt = PROMPT.format(
        catalogue=_format_catalogue(),
        documents=DOCUMENT_SUMMARY,
        suppliers=_known_entities(),
        question=question,
    )

    raw, api_error = None, None
    for attempt in range(4):
        try:
            response = _client.models.generate_content(
                model=MODEL, contents=prompt
            )
            raw = response.text
            break
        except Exception as e:
            api_error = f"{type(e).__name__}: {e}"
            wait = 10 * (attempt + 1)
            print(f"    API error, retrying in {wait}s")
            time.sleep(wait)

    if raw is None:
        return RoutingDecision(question, None, "", None, "",
                               error=f"API unavailable: {api_error}")

    try:
        parsed = json.loads(_strip_fences(raw))
    except json.JSONDecodeError as e:
        return RoutingDecision(question, None, "", None, raw,
                               error=f"unparseable response: {e}")

    return RoutingDecision(
        question=question,
        route=parsed.get("route"),
        reason=parsed.get("reason", ""),
        query_id=parsed.get("query_id"),
        supplier_id=parsed.get("supplier_id"),
        raw=raw,
    )