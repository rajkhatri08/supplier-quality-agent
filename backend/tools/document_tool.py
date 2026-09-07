"""The document retrieval tool.

Same contract as the SQL tool: never raises, returns structured results,
carries provenance.

Rewritten at Phase 9 to query Postgres with pgvector instead of Chroma. The
behaviour is unchanged — same chunks, same embeddings, same threshold — but
the vectors live beside the defect data rather than in an ephemeral file.

Phase 2 decided closed 8D reports stay retrievable but are separated from
open ones rather than penalised. A closed report is not less relevant — it is
differently relevant. It is the wrong answer to "what is failing now" and the
right answer to "has this happened before". A distance penalty would encode it
as less relevant, which is a different claim from the one Phase 2 made.

That separation does real work rather than being decorative: on the question
"why is SUP-003's weld porosity getting worse", the closed historical report
ranks ahead of the open current one on pure similarity. Without the grouping,
an agent answering a present-tense question would lead with a problem that was
fixed eighteen months ago.
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pgvector.psycopg import register_vector
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.embeddings import EmbeddingUnavailable, embed_query  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
_engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)

# Measured, not assumed. Across seven test questions the bands separated
# cleanly: relevant matches landed 0.22-0.33, a question about data that does
# not exist landed 0.385-0.388, and a wholly off-topic question landed
# 0.452-0.455. 0.35 sits in the gap with margin on both sides.
#
# Same discipline as App 1's distance tiering, which was calibrated before
# being kept — and then deleted when the calibration showed a 73.9% ceiling.
# A threshold nobody measured is a number nobody can defend.
RELEVANCE_THRESHOLD = 0.35

# <=> is pgvector's cosine distance operator, matching the metric Chroma was
# configured with. Distances are directly comparable to the measurements
# above.
SEARCH = """
    SELECT chunk_id, report_id, supplier_id, defect_code,
           discipline_title, status, opened_date, closed_date, title,
           chunk_text,
           embedding <=> CAST(:query_vec AS vector) AS distance
    FROM report_chunks
    {where}
    ORDER BY distance
    LIMIT :k
"""

DocFailureKind = Literal[
    "unavailable",     # embedding API or database unreachable
    "no_match",        # retrieval ran, nothing cleared the threshold
]


@dataclass
class Passage:
    chunk_id: str
    text: str
    distance: float
    report_id: str
    supplier_id: str
    defect_code: str
    discipline_title: str
    status: str
    opened_date: str
    closed_date: str
    title: str

    def citation(self) -> str:
        """How this passage should be attributed in an answer."""
        when = (f"closed {self.closed_date}" if self.closed_date
                else f"open since {self.opened_date}")
        return f"{self.report_id} ({when}), {self.discipline_title}"


@dataclass
class DocResult:
    ok: bool
    question: str
    open_passages: list[Passage] = field(default_factory=list)
    closed_passages: list[Passage] = field(default_factory=list)
    failure_kind: DocFailureKind | None = None
    reason: str | None = None

    @property
    def total(self) -> int:
        return len(self.open_passages) + len(self.closed_passages)

    def summary(self) -> str:
        if not self.ok:
            return f"{self.failure_kind}: {self.reason}"
        return (f"{len(self.open_passages)} passages from open reports, "
                f"{len(self.closed_passages)} from closed reports")


def search(question: str, k: int = 6,
           supplier_id: str | None = None) -> DocResult:
    """Retrieve passages. Returns a result; never raises.

    supplier_id narrows retrieval — useful when the question names a supplier
    and the router extracted it. Without the filter, "why is SUP-003 getting
    worse" returned five of six passages from a different supplier's report.
    """
    try:
        vector = embed_query(question)
    except EmbeddingUnavailable as e:
        return DocResult(ok=False, question=question,
                         failure_kind="unavailable", reason=str(e))

    where = "WHERE supplier_id = :supplier_id" if supplier_id else ""
    params = {"query_vec": str(vector), "k": k}
    if supplier_id:
        params["supplier_id"] = supplier_id

    try:
        with _engine.connect() as conn:
            register_vector(conn.connection.driver_connection)
            rows = conn.execute(
                text(SEARCH.format(where=where)), params
            ).all()
    except SQLAlchemyError as e:
        return DocResult(
            ok=False, question=question, failure_kind="unavailable",
            reason=f"could not query report_chunks: {type(e).__name__}",
        )

    if not rows:
        return DocResult(
            ok=False, question=question, failure_kind="no_match",
            reason="no passages found"
                   + (f" for supplier {supplier_id}" if supplier_id else ""),
        )

    open_passages, closed_passages = [], []
    for r in rows:
        if r.distance > RELEVANCE_THRESHOLD:
            continue
        passage = Passage(
            chunk_id=r.chunk_id,
            text=r.chunk_text,
            distance=round(r.distance, 4),
            report_id=r.report_id,
            supplier_id=r.supplier_id,
            defect_code=r.defect_code,
            discipline_title=r.discipline_title,
            status=r.status,
            opened_date=r.opened_date.isoformat(),
            closed_date=r.closed_date.isoformat() if r.closed_date else "",
            title=r.title,
        )
        if passage.status == "Open":
            open_passages.append(passage)
        else:
            closed_passages.append(passage)

    if not open_passages and not closed_passages:
        best = min(r.distance for r in rows)
        return DocResult(
            ok=False, question=question, failure_kind="no_match",
            reason=f"nothing within the relevance threshold "
                   f"({RELEVANCE_THRESHOLD}). Closest match was {best:.4f}.",
        )

    return DocResult(ok=True, question=question,
                     open_passages=open_passages,
                     closed_passages=closed_passages)