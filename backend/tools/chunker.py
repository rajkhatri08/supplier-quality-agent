"""Chunk 8D reports on discipline boundaries.

App 1's biggest single gain came from chunking on article boundaries rather
than fixed token windows — 78% to 95% on a 23-question eval set. The same
insight applies here: an 8D has eight disciplines, and those are the natural
boundaries.

The Phase 3 schema stores each discipline in its own column, so this needs no
parsing and cannot split mid-discipline. The chunking strategy shaped the
table design rather than being applied to it afterwards.

Each chunk carries the report's identity in its text as well as its metadata.
A retrieved D4 that reads "Electrode tip wear beyond the dressing interval"
with no other context is useless — the agent needs to know which report, which
supplier, and whether it is open or closed.
"""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
_engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)

# Column name mapped to the discipline's real title. The titles go into the
# chunk text: "D4: Root Cause" retrieves better than a bare column name, and
# it is what a quality engineer would call it.
DISCIPLINES = [
    ("d1_team",        "D1: Team"),
    ("d2_problem",     "D2: Problem Description"),
    ("d3_containment", "D3: Interim Containment Action"),
    ("d4_root_cause",  "D4: Root Cause"),
    ("d5_corrective",  "D5: Permanent Corrective Action"),
    ("d6_implemented", "D6: Implementation and Validation"),
    ("d7_prevent",     "D7: Prevent Recurrence"),
    ("d8_closure",     "D8: Closure"),
]


@dataclass
class Chunk:
    chunk_id: str          # '8D-2026-011#d4_root_cause'
    text: str
    report_id: str
    supplier_id: str
    defect_code: str
    part_id: str | None
    discipline: str        # 'd4_root_cause'
    discipline_title: str  # 'D4: Root Cause'
    status: str
    opened_date: str
    closed_date: str | None
    title: str

    def metadata(self) -> dict:
        """Chroma metadata. Must be flat scalars — no None, no nested types."""
        return {
            "report_id": self.report_id,
            "supplier_id": self.supplier_id,
            "defect_code": self.defect_code,
            "part_id": self.part_id or "",
            "discipline": self.discipline,
            "discipline_title": self.discipline_title,
            "status": self.status,
            "opened_date": self.opened_date,
            "closed_date": self.closed_date or "",
            "title": self.title,
        }


def fetch_reports() -> list[dict]:
    columns = ", ".join(
        ["report_id", "supplier_id", "defect_code", "part_id", "title",
         "opened_date", "closed_date", "status"]
        + [col for col, _ in DISCIPLINES]
    )
    with _engine.connect() as conn:
        result = conn.execute(text(f"SELECT {columns} FROM reports_8d"))
        keys = list(result.keys())
        return [dict(zip(keys, row)) for row in result.fetchall()]


def chunk_report(report: dict) -> list[Chunk]:
    chunks = []
    for column, discipline_title in DISCIPLINES:
        body = report[column]
        if not body or not body.strip():
            continue

        # Identity goes in the text, not only the metadata. A retrieved
        # chunk has to stand alone — the embedding should encode which
        # supplier and which report this discipline belongs to.
        status_note = (
            f"Status: {report['status']}"
            + (f", closed {report['closed_date']}" if report["closed_date"]
               else f", open since {report['opened_date']}")
        )
        text_block = (
            f"8D Report {report['report_id']} — {report['title']}\n"
            f"Supplier: {report['supplier_id']} | "
            f"Defect code: {report['defect_code']}\n"
            f"{status_note}\n\n"
            f"{discipline_title}\n{body.strip()}"
        )

        chunks.append(Chunk(
            chunk_id=f"{report['report_id']}#{column}",
            text=text_block,
            report_id=report["report_id"],
            supplier_id=report["supplier_id"],
            defect_code=report["defect_code"],
            part_id=report["part_id"],
            discipline=column,
            discipline_title=discipline_title,
            status=report["status"],
            opened_date=report["opened_date"].isoformat(),
            closed_date=(report["closed_date"].isoformat()
                         if report["closed_date"] else None),
            title=report["title"],
        ))
    return chunks


def chunk_all() -> list[Chunk]:
    chunks = []
    for report in fetch_reports():
        chunks.extend(chunk_report(report))
    return chunks


if __name__ == "__main__":
    all_chunks = chunk_all()
    reports = {c.report_id for c in all_chunks}
    print(f"{len(all_chunks)} chunks from {len(reports)} reports")
    print(f"expected: {len(reports) * len(DISCIPLINES)} if every discipline "
          f"is populated")

    lengths = [len(c.text) for c in all_chunks]
    print(f"chunk length: min {min(lengths)}, "
          f"mean {sum(lengths) // len(lengths)}, max {max(lengths)}")

    print("\n--- example: the D4 that matters ---")
    for c in all_chunks:
        if c.chunk_id == "8D-2026-011#d4_root_cause":
            print(c.text)
            print(f"\nmetadata: {c.metadata()}")