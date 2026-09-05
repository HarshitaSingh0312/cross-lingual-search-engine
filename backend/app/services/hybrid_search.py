from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Document
from app.services.retrieval_service import retrieval_service, run_inference

settings = get_settings()

RRF_K = 60  # standard smoothing constant from the original RRF paper - de-emphasizes rank 1 vs 2


class HybridSearchService:
    """Combines dense (cross-lingual, meaning-based) retrieval with BM25 (same-surface-form,
    keyword-exact) retrieval via Reciprocal Rank Fusion, then re-scores the fused candidate
    pool with a multilingual cross-encoder for a final precision pass.

    BM25 runs over ALL documents in one shared index, not split per language: splitting would
    need reliable query-language detection, which Phase 4 deliberately deferred. A single mixed
    index still earns its keep on cases dense embeddings weaken on - exact rare terms, numbers,
    acronyms, and proper nouns, which are largely language-invariant anyway (e.g. "COVID-19"
    reads the same in an English, Spanish, or French document).

    The cross-encoder only ever scores a short candidate list, never the full corpus - it's far
    more accurate than cosine similarity (it reads the query and doc together, not as two
    separately-encoded vectors) but too slow to run on every document per query.
    """

    def __init__(self) -> None:
        self.bm25: BM25Okapi | None = None
        self.doc_ids: list[str] = []
        self.cross_encoder: CrossEncoder | None = None

    async def load(self, db: AsyncSession) -> None:
        if self.bm25 is not None:
            return
        rows = (await db.execute(select(Document.id, Document.title, Document.summary))).all()
        self.doc_ids = [row.id for row in rows]
        tokenized = [f"{row.title} {row.summary}".lower().split() for row in rows]
        self.bm25 = BM25Okapi(tokenized)
        self.cross_encoder = CrossEncoder(settings.cross_encoder_model_name)

    def _bm25_ranked_ids(self, query: str, top_n: int) -> list[str]:
        scores = self.bm25.get_scores(query.lower().split())
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_n]
        return [self.doc_ids[i] for i in ranked if scores[i] > 0]

    @staticmethod
    def reciprocal_rank_fusion(ranked_lists: list[list[str]], k: int = RRF_K) -> dict[str, float]:
        fused: dict[str, float] = {}
        for ranked in ranked_lists:
            for rank, doc_id in enumerate(ranked, start=1):
                fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank)
        return fused

    async def search(self, db: AsyncSession, query: str, top_k: int = 10) -> list[dict]:
        # Pools scale with top_k so a large top_k request still has enough candidates left
        # after fusion to rerank - fixed pool sizes would silently truncate big requests.
        retrieval_pool = max(30, top_k * 3)
        rerank_pool = max(20, top_k * 2)

        dense_results = await retrieval_service.search(db, query, top_k=retrieval_pool)
        dense_by_id = {r["doc_id"]: r for r in dense_results}
        dense_ranked_ids = [r["doc_id"] for r in dense_results]

        bm25_ranked_ids = self._bm25_ranked_ids(query, retrieval_pool)

        fused = self.reciprocal_rank_fusion([dense_ranked_ids, bm25_ranked_ids])
        candidate_ids = sorted(fused, key=fused.get, reverse=True)[:rerank_pool]

        # BM25-only hits won't have title/summary from the dense pass yet.
        missing_ids = [cid for cid in candidate_ids if cid not in dense_by_id]
        docs_by_id = dict(dense_by_id)
        if missing_ids:
            rows = (await db.execute(select(Document).where(Document.id.in_(missing_ids)))).scalars().all()
            for doc in rows:
                docs_by_id[doc.id] = {
                    "doc_id": doc.id,
                    "title": doc.title,
                    "summary": doc.summary,
                    "language": doc.language,
                    "url": doc.url,
                    "score": 0.0,
                }

        pairs = [(query, f"{docs_by_id[cid]['title']} {docs_by_id[cid]['summary']}") for cid in candidate_ids]
        # Same event-loop-blocking issue as the dense encoder (see retrieval_service.search),
        # and worse here - the cross-encoder pass is this app's single slowest call. Goes
        # through the same throttled run_inference (not a bare to_thread) so a burst of hybrid
        # searches shares the same concurrent-inference budget as plain dense searches instead
        # of each fanning out independently - see retrieval_service.py's module-level comment.
        rerank_scores = await run_inference(self.cross_encoder.predict, pairs) if pairs else []
        reranked = sorted(zip(candidate_ids, rerank_scores), key=lambda pair: pair[1], reverse=True)[:top_k]

        results = []
        for doc_id, score in reranked:
            result = dict(docs_by_id[doc_id])
            result["score"] = float(score)
            results.append(result)
        return results


hybrid_search_service = HybridSearchService()
