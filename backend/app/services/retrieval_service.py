import asyncio
import os

import torch
from sentence_transformers import SentenceTransformer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Document, Embedding

settings = get_settings()

# Phase 12's load test tried two extremes and both failed: unlimited torch threads per call
# with unlimited concurrent calls oversubscribed the host badly enough to crash Docker itself
# (each concurrent encode call fought every other for all cores); pinning torch to 1 thread
# avoided that but made each individual cross-encoder batch call ~much~ slower, since it lost
# all intra-op matmul parallelism it actually benefits from. The real fix is bounding both
# numbers so their product roughly matches the host's real core budget: each call gets a few
# threads to itself, and a semaphore caps how many such calls run at once.
_TORCH_THREADS_PER_CALL = 4
_INFERENCE_CONCURRENCY = max(1, (os.cpu_count() or 4) // _TORCH_THREADS_PER_CALL)
_inference_semaphore = asyncio.Semaphore(_INFERENCE_CONCURRENCY)


async def run_inference(fn, *args):
    """Runs a synchronous, CPU-bound torch call (embedding encode, cross-encoder predict) off
    the event loop, throttled to _INFERENCE_CONCURRENCY concurrent calls - see the comment
    above for why neither "unlimited threads" nor "1 thread, unlimited concurrency" alone is
    safe for this host. Shared by HybridSearchService's cross-encoder call, not just search()
    below, since both do the same kind of CPU-bound torch inference."""
    async with _inference_semaphore:
        return await asyncio.to_thread(fn, *args)


class RetrievalService:
    """Encodes queries with the same multilingual model/normalization used to build the
    stored document embeddings (see cross_lingual_retrieval/src/dense_retrieval.py), then
    searches via pgvector cosine distance instead of that module's in-memory FAISS index —
    FAISS stays an offline benchmarking tool per PROJECT_PLAN.md Section 2; pgvector is what
    runs in production so vector search lives next to the relational data, one fewer moving part.

    DenseRetriever itself isn't instantiated here: its __init__ has script-oriented side effects
    (creates a `data/embeddings/` dir relative to cwd) that don't fit a long-running server process.
    """

    def __init__(self) -> None:
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model: SentenceTransformer | None = None

    def load(self) -> None:
        # Process-global setting, so it's made once here (the first model loaded at startup)
        # rather than repeated in HybridSearchService.load() for the cross-encoder - see the
        # module-level comment above for why this number, paired with _INFERENCE_CONCURRENCY,
        # isn't just "more threads = faster."
        torch.set_num_threads(_TORCH_THREADS_PER_CALL)
        self.model = SentenceTransformer(settings.embedding_model_name).to(self.device)

    def encode_query(self, query: str) -> list[float]:
        # No manual L2-normalization: pgvector's cosine_distance operator computes true
        # cosine similarity from the raw vectors, unlike the original FAISS IndexFlatIP
        # setup which needed pre-normalized vectors to approximate cosine via inner product.
        embedding = self.model.encode([query], convert_to_numpy=True, device=self.device)[0]
        return embedding.tolist()

    async def search(self, db: AsyncSession, query: str, top_k: int = 10) -> list[dict]:
        # Load-testing (Phase 12) showed this call, run inline, blocked the whole single-process
        # event loop for its full duration - one slow encode stalled every other concurrent
        # request. run_inference offloads it to a throttled worker thread (see module-level
        # comment); torch's actual compute releases the GIL while running, so other requests
        # genuinely keep progressing, not just avoid a stall.
        query_vector = await run_inference(self.encode_query, query)
        distance = Embedding.vector.cosine_distance(query_vector)
        stmt = (
            select(Document, distance.label("distance"))
            .join(Embedding, Embedding.document_id == Document.id)
            .order_by(distance)
            .limit(top_k)
        )
        rows = (await db.execute(stmt)).all()
        return [
            {
                "doc_id": doc.id,
                "title": doc.title,
                "summary": doc.summary,
                "language": doc.language,
                "url": doc.url,
                "score": 1 - dist,
            }
            for doc, dist in rows
        ]


retrieval_service = RetrievalService()
