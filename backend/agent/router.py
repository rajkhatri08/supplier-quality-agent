"""The router.

Chooses between the SQL tool, the document tool, both, or neither — and
states why. The reason is not decoration: Phase 8 shows it, and a routing
decision nobody can explain fails the depth bar this project is aimed at.

The model sees the query catalogue's descriptions and a summary of what the
documents contain. It does not see SQL, and it does not write SQL: it names a
route and, for SQL routes, names a query from the fixed catalogue.

Change log, measured against eval/routing-set.json:
  baseline  18/24 (75%), BOTH 1/6.
            Five of six BOTH questions went to DOCS, each with a true reason
            — the explanation does live in the reports. The prompt described
            what a SQL-only answer would be missing ("its reason") but had no
            equivalent for what a DOCS-only answer would be missing. The
            router was answering "where does the explanation live?" when the
            question is "what would a complete answer need?"
  change 1  BOTH criterion made bidirectional: check whether a DOCS-only
            answer would be an explanation with no evidence, as well as
            whether a SQL-only answer would be a number with no reason.
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

QUESTION: {question}

Reply with JSON and nothing else:
{{"route": "SQL|DOCS|BOTH|NEITHER", "reason": "one sentence", \
"query_id": "catalogue query id, or null"}}"""


@dataclass
class RoutingDecision:
    question: str
    route: Route | None
    reason: str
    query_id: str | None
    raw: str
    error: str | None = None


def _format_catalogue() -> str:
    return "\n".join(
        f"   - {e['query_id']}: {e['description']}"
        for e in catalogue_manifest()
    )


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
        raw=raw,
    )