"""Re-run Q11 and Q12 only. Their tier 2 attempt failed on DNS resolution,
not on the SQL — infrastructure noise, so they are not scored as failures."""

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
    (11, "For each commodity, which single part had the worst PPM over the "
         "last 12 months of the window? The window ends August 2026."),
    (12, "Which parts had a defect PPM above their own supplier's average PPM "
         "over the full window?"),
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


def main() -> None:
    results = []
    for num, question in QUESTIONS:
        print(f"\n{'=' * 70}\nQ{num}  {question}\n{'=' * 70}")

        raw = None
        for attempt in range(4):
            try:
                r = client.models.generate_content(
                    model=MODEL,
                    contents=PROMPT.format(schema=SCHEMA, question=question),
                )
                raw = r.text
                break
            except Exception as e:
                wait = 15 * (attempt + 1)
                print(f"  API error, retrying in {wait}s — {type(e).__name__}")
                time.sleep(wait)

        if raw is None:
            print("  API unavailable after 4 attempts")
            continue

        sql = strip_fences(raw)
        print(f"\n--- generated SQL ---\n{sql}")

        try:
            with engine.connect() as conn:
                rows = [list(r) for r in conn.execute(text(sql)).fetchall()]
            print(f"\n--- result ({len(rows)} rows) ---")
            for r in rows[:20]:
                print(" ", r)
            if len(rows) > 20:
                print(f"  ... {len(rows) - 20} more")
            error = None
        except Exception as e:
            rows, error = None, f"{type(e).__name__}: {e}"
            print(f"\n--- FAILURE ---\n{error}")

        results.append({"q": num, "question": question, "sql": sql,
                        "rows": rows, "error": error})

    out = SPIKE_DIR / "spike_run_tier2_rerun.json"
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nwritten: {out}")


if __name__ == "__main__":
    main()