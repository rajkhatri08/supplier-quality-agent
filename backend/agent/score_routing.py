"""Score the router against the frozen eval set.

Reports accuracy overall and per label. Per-label matters more than the
headline: an agent that routes everything BOTH scores 25% and looks like it
is being thorough.
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent.router import route  # noqa: E402

EVAL_PATH = Path(__file__).resolve().parents[2] / "eval" / "routing-set.json"


def main() -> None:
    data = json.loads(EVAL_PATH.read_text())
    questions = data["questions"]

    results = []
    for q in questions:
        decision = route(q["question"])
        correct = decision.route == q["label"]
        results.append({
            "id": q["id"],
            "question": q["question"],
            "expected": q["label"],
            "got": decision.route,
            "correct": correct,
            "reason": decision.reason,
            "query_id": decision.query_id,
            "error": decision.error,
        })
        mark = "ok  " if correct else "MISS"
        got = decision.route or f"ERROR({decision.error})"
        print(f"{mark} {q['id']:8} expected {q['label']:8} got {got}")
        if not correct and decision.reason:
            print(f"         reason: {decision.reason}")

    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    print(f"\n{'=' * 60}")
    print(f"accuracy: {correct}/{total} = {100 * correct / total:.1f}%")

    print("\nper label:")
    by_label = {}
    for r in results:
        by_label.setdefault(r["expected"], []).append(r["correct"])
    for label in ["SQL", "DOCS", "BOTH", "NEITHER"]:
        if label in by_label:
            hits = sum(by_label[label])
            n = len(by_label[label])
            print(f"  {label:8} {hits}/{n}")

    print("\nwhat it chose (all questions):")
    for choice, n in Counter(r["got"] for r in results).most_common():
        print(f"  {choice}: {n}")

    out = Path(__file__).resolve().parent / "routing_baseline.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nwritten: {out.name}")


if __name__ == "__main__":
    main()