"""Build the Chroma index from 8D report chunks.

Rebuilds from scratch each run. With 96 chunks that takes seconds, and it
means the index is always a pure function of what is in Postgres — no drift
between the database and the vector store.

That property matters for Phase 9: Render's filesystem is ephemeral and resets
on every deploy, so the index has to rebuild at startup anyway. Making rebuild
the normal path rather than a recovery path means the deployed behaviour is
the behaviour that gets tested.
"""

import sys
from pathlib import Path

import chromadb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.chunker import chunk_all  # noqa: E402
from tools.embeddings import embed_documents  # noqa: E402

INDEX_DIR = Path(__file__).resolve().parents[1] / "chroma_index"
COLLECTION = "reports_8d"


def build_index() -> int:
    chunks = chunk_all()
    print(f"chunked {len(chunks)} passages from the 8D reports")

    print("embedding...")
    vectors = embed_documents([c.text for c in chunks])

    client = chromadb.PersistentClient(path=str(INDEX_DIR))

    # Delete and recreate rather than upsert. The index should be a pure
    # function of the database; upserting leaves orphans behind when a
    # report is removed or a discipline is edited.
    try:
        client.delete_collection(COLLECTION)
        print(f"dropped existing collection")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    collection.add(
        ids=[c.chunk_id for c in chunks],
        documents=[c.text for c in chunks],
        embeddings=vectors,
        metadatas=[c.metadata() for c in chunks],
    )

    print(f"indexed {collection.count()} chunks into {INDEX_DIR.name}/")
    return collection.count()


if __name__ == "__main__":
    count = build_index()

    client = chromadb.PersistentClient(path=str(INDEX_DIR))
    collection = client.get_collection(COLLECTION)

    print("\n--- verification ---")
    print(f"count: {collection.count()}")

    sample = collection.get(ids=["8D-2026-011#d4_root_cause"])
    print(f"\nspot check — 8D-2026-011 D4:")
    print(f"  metadata: {sample['metadatas'][0]}")
    print(f"  text starts: {sample['documents'][0][:80]}...")

    open_chunks = collection.get(where={"status": "Open"})
    closed_chunks = collection.get(where={"status": "Closed"})
    print(f"\nstatus split: {len(open_chunks['ids'])} open, "
          f"{len(closed_chunks['ids'])} closed")