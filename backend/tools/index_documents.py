"""Build the vector index in Postgres.

Rewritten at Phase 9. Chroma was dropped because it pulled 200 MB of unused
transitive dependencies and a clean deploy install measured 476 MB against
Render's 512 MB limit.

Postgres was the better answer for a second reason: Render's filesystem is
ephemeral, so a Chroma index had to be rebuilt on every deploy and every cold
start. Vectors in the database do not disappear.

The index is still a pure function of reports_8d — this deletes and rebuilds
rather than upserting, so a changed report cannot leave an orphaned chunk
behind.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pgvector.psycopg import register_vector
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.chunker import chunk_all  # noqa: E402
from tools.embeddings import embed_documents  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
_engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)

INSERT = text("""
    INSERT INTO report_chunks (
        chunk_id, report_id, supplier_id, defect_code,
        discipline, discipline_title, status,
        opened_date, closed_date, title, chunk_text, embedding
    ) VALUES (
        :chunk_id, :report_id, :supplier_id, :defect_code,
        :discipline, :discipline_title, :status,
        :opened_date, :closed_date, :title, :chunk_text, :embedding
    )
""")


def build_index() -> int:
    chunks = chunk_all()
    print(f"chunked {len(chunks)} passages from the 8D reports")

    print("embedding...")
    vectors = embed_documents([c.text for c in chunks])

    with _engine.begin() as conn:
        # register_vector teaches psycopg how to send a Python list as a
        # pgvector value. Without it the insert fails on the embedding column.
        register_vector(conn.connection.driver_connection)

        conn.execute(text("DELETE FROM report_chunks"))

        for chunk, vector in zip(chunks, vectors):
            conn.execute(INSERT, {
                "chunk_id": chunk.chunk_id,
                "report_id": chunk.report_id,
                "supplier_id": chunk.supplier_id,
                "defect_code": chunk.defect_code,
                "discipline": chunk.discipline,
                "discipline_title": chunk.discipline_title,
                "status": chunk.status,
                "opened_date": chunk.opened_date,
                "closed_date": chunk.closed_date,
                "title": chunk.title,
                "chunk_text": chunk.text,
                "embedding": vector,
            })

    with _engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM report_chunks")).scalar()

    print(f"indexed {count} chunks into report_chunks")
    return count


if __name__ == "__main__":
    build_index()

    with _engine.connect() as conn:
        print("\n--- verification ---")
        rows = conn.execute(text(
            "SELECT status, COUNT(*) FROM report_chunks GROUP BY status"
        )).all()
        for status, n in rows:
            print(f"  {status}: {n}")

        sample = conn.execute(text(
            "SELECT chunk_id, discipline_title, "
            "       vector_dims(embedding) AS dims "
            "FROM report_chunks WHERE chunk_id = '8D-2026-011#d4_root_cause'"
        )).first()
        print(f"\n  spot check: {sample.chunk_id}")
        print(f"    {sample.discipline_title}, {sample.dims} dimensions")