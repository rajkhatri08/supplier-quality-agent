"""Gemini embeddings.

App 1 used the same approach — Chroma for storage, Gemini for embeddings, no
local model. Keeps PyTorch out of the deploy, which matters on a 512 MB tier.

Document embeddings are computed once at index time. Only the query embedding
is live, so a network failure degrades retrieval rather than breaking it —
the tool returns 'unavailable' the same way the SQL tool does.
"""

import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

MODEL = "gemini-embedding-001"

# Documents and queries are embedded with different task types. The model
# places a question and the passage that answers it closer together than a
# symmetric embedding would.
DOCUMENT = "RETRIEVAL_DOCUMENT"
QUERY = "RETRIEVAL_QUERY"


class EmbeddingUnavailable(RuntimeError):
    """The embedding API could not be reached."""


def _embed(texts: list[str], task_type: str) -> list[list[float]]:
    last_error = None
    for attempt in range(4):
        try:
            response = _client.models.embed_content(
                model=MODEL,
                contents=texts,
                config=types.EmbedContentConfig(task_type=task_type),
            )
            return [e.values for e in response.embeddings]
        except Exception as e:
            last_error = e
            wait = 5 * (attempt + 1)
            print(f"  embedding error, retrying in {wait}s — "
                  f"{type(e).__name__}")
            time.sleep(wait)
    raise EmbeddingUnavailable(
        f"embedding API unavailable after 4 attempts: {type(last_error).__name__}"
    )


def embed_documents(texts: list[str], batch_size: int = 20) -> list[list[float]]:
    """Embed chunks for indexing. Batched — 96 separate calls would be slow
    and would hit rate limits."""
    vectors = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        vectors.extend(_embed(batch, DOCUMENT))
        print(f"  embedded {min(i + batch_size, len(texts))}/{len(texts)}")
    return vectors


def embed_query(question: str) -> list[float]:
    """Embed a single question for retrieval."""
    return _embed([question], QUERY)[0]


if __name__ == "__main__":
    vec = embed_query("why is SUP-003's weld porosity getting worse?")
    print(f"query embedding: {len(vec)} dimensions")
    print(f"first 5 values: {[round(v, 4) for v in vec[:5]]}")