"""Retrieval tests.

Distances are printed raw so a relevance threshold can be set from
measurement rather than assumption. The last two questions have no relevant
documents at all — whatever they return is the noise floor.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.document_tool import search  # noqa: E402

QUESTIONS = [
    "why is SUP-003's weld porosity getting worse?",
    "has weld porosity happened before at SUP-003?",
    "what caused the roof rail splitting?",
    "what is being done about sealer skips on door hem flanges?",
    "which suppliers have open quality issues?",
    "what is the on-time delivery rate?",          # nothing relevant exists
    "how do I bake a cake?",                       # completely off-topic
]

for question in QUESTIONS:
    print(f"\n{'=' * 74}\n{question}\n{'=' * 74}")
    result = search(question, k=5)
    print(f"  {result.summary()}")

    if not result.ok:
        continue

    if result.open_passages:
        print("\n  OPEN reports:")
        for p in result.open_passages:
            print(f"    {p.distance:.4f}  {p.citation()}")
            print(f"             {p.text.splitlines()[-1][:80]}")

    if result.closed_passages:
        print("\n  CLOSED reports (history):")
        for p in result.closed_passages:
            print(f"    {p.distance:.4f}  {p.citation()}")
            print(f"             {p.text.splitlines()[-1][:80]}")