"""Phase 1 spike harness — text-to-SQL against the frozen question set.

Feeds each question plus the raw schema DDL to Gemini, runs whatever SQL
comes back, and records the result. Grading is done by hand against the
expected answers in docs/spike-text-to-sql.md.

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

QUESTIONS = [
    "How many defect events were recorded against SUP-003 parts in 2026?",
    "Which vehicle system has the most defect events across the whole window?",
    "What was the total production volume for Weld Assemblies suppliers in the "
    "last 12 months of the window? The window ends August 2026.",
    "Which defect code appears most often on parts supplied by SUP-009?",
    "What was SUP-003's defect PPM in August 2026?",
    "For each commodity, what is the average monthly PPM over the full "
    "24-month window?",
    "Which part had the largest single-month increase in defect units "
    "compared with its own previous month?",
    "Which suppliers had a higher total defect count but a lower defect PPM "
    "than SUP-003 over the last 12 months? The window ends August 2026.",
    "For Critical-severity defects only, which supplier had the worst PPM in "
    "the final 6 months of the window, and what was it? The window ends "
    "August 2026.",
    "Which defect codes were never recorded against any SUP-005 part?",
]

PROMPT = """You are given a PostgreSQL schema. Write one SQL query that \
answers the question.

Schema:
{schema}

Question: {question}

Return only the SQL query. No explanation, no markdown fences."""

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
engine = create_engine(os.environ["DATABASE_URL"])


def strip_fences(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^```(?:sql)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()


def run(sql: str):
    """Returns (rows, error). Read-only: never commits."""
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(sql)).fetchall()
        return [list(r) for r in rows], None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def main() -> None:
    results = []
    for i, question in enumerate(QUESTIONS, start=1):
        print(f"\n{'=' * 70}\nQ{i}  {question}\n{'=' * 70}")

        # Retry transient API failures. An API failure is neither a hard nor
        # a silent failure — it says nothing about SQL correctness — so these
        # questions are re-run rather than scored.
        sql, api_error = None, None
        for attempt in range(4):
            try:
                response = client.models.generate_content(
                    model=MODEL,
                    contents=PROMPT.format(schema=SCHEMA, question=question),
                )
                sql = strip_fences(response.text)
                break
            except Exception as e:
                api_error = f"{type(e).__name__}: {e}"
                wait = 15 * (attempt + 1)
                print(f"  API error, retrying in {wait}s — {api_error[:90]}")
                time.sleep(wait)

        if sql is None:
            print(f"\n--- API UNAVAILABLE after 4 attempts ---\n{api_error}")
            results.append({
                "q": i,
                "question": question,
                "sql": None,
                "rows": None,
                "error": f"API: {api_error}",
            })
            continue

        print(f"\n--- generated SQL ---\n{sql}")

        rows, error = run(sql)
        if error:
            print(f"\n--- HARD FAILURE ---\n{error}")
        else:
            print(f"\n--- result ({len(rows)} rows) ---")
            for r in rows[:15]:
                print(" ", r)
            if len(rows) > 15:
                print(f"  ... {len(rows) - 15} more")

        results.append({
            "q": i,
            "question": question,
            "sql": sql,
            "rows": rows,
            "error": error,
        })

    out = SPIKE_DIR / "spike_run.json"
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"\n\nwritten: {out}")

    hard = sum(1 for r in results
               if r["error"] and not r["error"].startswith("API:"))
    unavailable = sum(1 for r in results
                      if r["error"] and r["error"].startswith("API:"))
    print(f"hard failures:     {hard} / {len(results)}")
    print(f"API unavailable:   {unavailable} / {len(results)}  (re-run these)")
    print("silent failures:   grade by hand against the expected answers")


if __name__ == "__main__":
    main()