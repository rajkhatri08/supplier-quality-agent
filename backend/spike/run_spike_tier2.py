"""Phase 1 tier 2 harness — 8 well-posed + 7 adversarial questions.

Tier 2a uses the same prompt as tier 1. Tier 2b uses a prompt that permits a
non-SQL answer, because forcing SQL output would make the adversarial
questions measure the prompt rather than the model.

Throwaway. Deleted once the decision is recorded.
"""

import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from sqlalchemy import create_engine, text

SPIKE_DIR = Path(__file__).resolve().parent
load_dotenv(SPIKE_DIR.parent / ".env")

MODEL = "gemini-3.6-flash"
SCHEMA = (SPIKE_DIR / "schema.sql").read_text()

TIER_2A = [
    (11, "For each commodity, which single part had the worst PPM over the "
         "last 12 months of the window? The window ends August 2026."),
    (12, "Which parts had a defect PPM above their own supplier's average PPM "
         "over the full window?"),
    (13, "Which suppliers' PPM was worse in the last 12 months than in the "
         "first 12 months, and by how much? The window ends August 2026."),
    (14, "Ranking suppliers by Critical defects only, how does the order "
         "differ from ranking them by all defects?"),
    (15, "For each vehicle system, what share of its defect units came from "
         "Critical-severity codes?"),
    (16, "Which part-months had defect units more than double that part's own "
         "24-month average?"),
    (17, "Among suppliers with more than 4 parts, which had the lowest PPM in "
         "the final 6 months of the window? The window ends August 2026."),
    (18, "For SUP-003, which defect code accounts for the largest share of "
         "its defect units, and what percentage is that?"),
]

TIER_2B = [
    (19, "What was SUP-003's on-time delivery rate in 2026?"),
    (20, "Why did SUP-011's PPM spike in March 2026?"),
    (21, "How many defects did SUP-003 have?"),
    (22, "What was PN-1042's PPM on 15 November 2025?"),
    (23, "Which operator was working when the D-WLD-01 defects were found?"),
    (24, "List the suppliers whose 8D reports are still open."),
    (25, "Which supplier is the worst?"),
]

PROMPT_2A = """You are given a PostgreSQL schema. Write one SQL query that \
answers the question.

Schema:
{schema}

Question: {question}

Return only the SQL query. No explanation, no markdown fences."""

# Permits refusal. Forcing SQL output here would measure the prompt, not the
# model — the correct answer to several of these is that they cannot be
# answered from this schema.
PROMPT_2B = """You are given a PostgreSQL schema and a question.

If the question can be answered from this schema, reply with the SQL query \
and nothing else.

If it cannot — because the data does not exist, because it refers to \
something not in the schema, or because the question is ambiguous — say so \
plainly instead of writing SQL. If it is ambiguous, state which \
interpretation you would use.

Schema:
{schema}

Question: {question}"""

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
engine = create_engine(os.environ["DATABASE_URL"])


def strip_fences(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^```(?:sql)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()


def looks_like_sql(s: str) -> bool:
    head = s.lstrip().upper()
    return head.startswith("SELECT") or head.startswith("WITH")


def ask(prompt: str):
    """Returns (text, error). Retries transient API failures."""
    err = None
    for attempt in range(4):
        try:
            r = client.models.generate_content(model=MODEL, contents=prompt)
            return r.text, None
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            wait = 15 * (attempt + 1)
            print(f"  API error, retrying in {wait}s — {err[:80]}")
            time.sleep(wait)
    return None, err


def run(sql: str):
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(sql)).fetchall()
        return [list(r) for r in rows], None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def main() -> None:
    results = []

    for tier, questions, prompt in [
        ("2a", TIER_2A, PROMPT_2A),
        ("2b", TIER_2B, PROMPT_2B),
    ]:
        for num, question in questions:
            print(f"\n{'=' * 70}\nQ{num}  [{tier}]  {question}\n{'=' * 70}")

            raw, api_error = ask(prompt.format(schema=SCHEMA, question=question))
            if raw is None:
                print(f"\n--- API UNAVAILABLE ---\n{api_error}")
                results.append({"q": num, "tier": tier, "question": question,
                                "raw": None, "sql": None, "rows": None,
                                "error": f"API: {api_error}"})
                continue

            body = strip_fences(raw)

            # Tier 2b may legitimately answer in prose. Only execute SQL.
            if not looks_like_sql(body):
                print(f"\n--- NON-SQL RESPONSE ---\n{body}")
                results.append({"q": num, "tier": tier, "question": question,
                                "raw": raw, "sql": None, "rows": None,
                                "error": None})
                continue

            print(f"\n--- generated SQL ---\n{body}")
            rows, error = run(body)
            if error:
                print(f"\n--- HARD FAILURE ---\n{error}")
            else:
                print(f"\n--- result ({len(rows)} rows) ---")
                for r in rows[:15]:
                    print(" ", r)
                if len(rows) > 15:
                    print(f"  ... {len(rows) - 15} more")

            results.append({"q": num, "tier": tier, "question": question,
                            "raw": raw, "sql": body, "rows": rows,
                            "error": error})

    out = SPIKE_DIR / "spike_run_tier2.json"
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"\n\nwritten: {out}")

    hard = sum(1 for r in results
               if r["error"] and not r["error"].startswith("API:"))
    unavailable = sum(1 for r in results
                      if r["error"] and r["error"].startswith("API:"))
    non_sql = sum(1 for r in results
                  if r["sql"] is None and r["error"] is None)
    print(f"hard failures:      {hard} / {len(results)}")
    print(f"API unavailable:    {unavailable} / {len(results)}")
    print(f"non-SQL responses:  {non_sql} / {len(results)}  (expected in 2b)")
    print("silent failures:    grade by hand")


if __name__ == "__main__":
    main()