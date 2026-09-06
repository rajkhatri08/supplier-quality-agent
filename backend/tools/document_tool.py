"""The document retrieval tool.

Same contract as the SQL tool: never raises, returns structured results,
carries provenance.

Phase 2 decided closed 8D reports stay retrievable but are separated from open
ones rather than penalised. A closed report is not less relevant — it is
differently relevant. It is the wrong answer to "what is failing now" and the
right answer to "has this happened before". A distance penalty would encode it
as less relevant, which is a different claim from the one Phase 2 made.

That separation turned out to do real work rather than being decorative: on
the question "why is SUP-003's weld porosity getting worse", the closed
historical report ranks ahead of the open current one on pure similarity.
Without the grouping, an agent answering a present-tense question would lead
with a problem that was fixed eighteen months ago.
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import chromadb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.embeddings import EmbeddingUnavailable, embed_query  # noqa: E402

INDEX_DIR = Path(__file__).resolve().parents[1] / "chroma_index"
COLLECTION = "reports_8d"

# Measured, not assumed. Across seven test questions the bands separated
# cleanly: relevant matches landed 0.22-0.33, a question about data that does
# not exist landed 0.385-0.388, and a wholly off-topic question landed
# 0.452-0.455. 0.35 sits in the gap with margin on both sides.
#
# Same discipline as App 1's distance tiering, which was calibrated before
# being kept — and then deleted when the calibration showed a 73.9% ceiling.
# A threshold nobody measured is a number nobody can defend.
RELEVANCE_THRESHOLD = 0.35

DocFailureKind = Literal[
    "unavailable",     # embedding API unreachable
    "index_missing",   # no collection — on Render, the startup rebuild failed
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


def _to_passage(doc: str, meta: dict[str, Any], distance: float,
                chunk_id: str) -> Passage:
    return Passage(
        chunk_id=chunk_id,
        text=doc,
        distance=round(distance, 4),
        report_id=meta["report_id"],
        supplier_id=meta["supplier_id"],
        defect_code=meta["defect_code"],
        discipline_title=meta["discipline_title"],
        status=meta["status"],
        opened_date=meta["opened_date"],
        closed_date=meta["closed_date"],
        title=meta["title"],
    )


def search(question: str, k: int = 6,
           supplier_id: str | None = None) -> DocResult:
    """Retrieve passages. Returns a result; never raises.

    supplier_id narrows retrieval via metadata filter — useful when the
    question already names a supplier and the agent knows it.
    """
    try:
        vector = embed_query(question)
    except EmbeddingUnavailable as e:
        return DocResult(ok=False, question=question,
                         failure_kind="unavailable", reason=str(e))

    try:
        client = chromadb.PersistentClient(path=str(INDEX_DIR))
        collection = client.get_collection(COLLECTION)
    except Exception as e:
        return DocResult(
            ok=False, question=question, failure_kind="index_missing",
            reason=f"could not open collection {COLLECTION!r}: "
                   f"{type(e).__name__}. Run index_documents.py.",
        )

    where = {"supplier_id": supplier_id} if supplier_id else None
    result = collection.query(
        query_embeddings=[vector], n_results=k, where=where,
    )

    ids = result["ids"][0]
    if not ids:
        return DocResult(
            ok=False, question=question, failure_kind="no_match",
            reason="no passages returned"
                   + (f" for supplier {supplier_id}" if supplier_id else ""),
        )

    open_passages, closed_passages = [], []
    for chunk_id, doc, meta, dist in zip(
        ids, result["documents"][0], result["metadatas"][0],
        result["distances"][0],
    ):
        if dist > RELEVANCE_THRESHOLD:
            continue
        passage = _to_passage(doc, meta, dist, chunk_id)
        if passage.status == "Open":
            open_passages.append(passage)
        else:
            closed_passages.append(passage)

    if not open_passages and not closed_passages:
        best = min(result["distances"][0])
        return DocResult(
            ok=False, question=question, failure_kind="no_match",
            reason=f"nothing within the relevance threshold "
                   f"({RELEVANCE_THRESHOLD}). Closest match was {best:.4f}.",
        )

    return DocResult(ok=True, question=question,
                     open_passages=open_passages,
                     closed_passages=closed_passages)