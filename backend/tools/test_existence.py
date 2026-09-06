"""Existence checks: real identifiers pass, well-formed fakes are rejected."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.existence import (  # noqa: E402
    check_supplier, check_part, check_defect_code, UnknownEntity,
)

SHOULD_PASS = [
    ("supplier SUP-003", check_supplier, "SUP-003"),
    ("part PN-1042", check_part, "PN-1042"),
    ("code D-WLD-01", check_defect_code, "D-WLD-01"),
    ("code D-SLR-03", check_defect_code, "D-SLR-03"),
]

SHOULD_FAIL = [
    ("supplier SUP-011 (Q20 false premise)", check_supplier, "SUP-011"),
    ("supplier SUP-999", check_supplier, "SUP-999"),
    ("part PN-9999", check_part, "PN-9999"),
    ("code D-WLD-09", check_defect_code, "D-WLD-09"),
    ("code D-XXX-01", check_defect_code, "D-XXX-01"),
]

print("--- should pass ---")
for label, fn, value in SHOULD_PASS:
    fn(value)
    print(f"  ok   {label}")

print("\n--- should fail ---")
for label, fn, value in SHOULD_FAIL:
    try:
        fn(value)
        print(f"  MISS {label}: accepted, should have been rejected")
    except UnknownEntity as e:
        print(f"  ok   {label}")
        print(f"       {e}")
