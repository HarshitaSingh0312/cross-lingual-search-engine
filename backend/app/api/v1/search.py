import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_optional_current_user
from app.core.config import get_settings
from app.db.base import get_db
from app.db.models import Document, SearchQuery, SearchResult, User
from app.schemas.rag import RagCitation, RagRequest, RagResponse
from app.schemas.search import SearchResponse
from app.services.cache_service import cache_service
from app.services.hybrid_search import hybrid_search_service
from app.services.rag_service import extract_cited_numbers, rag_service
from app.services.retrieval_service import retrieval_service

router = APIRouter(tags=["search"])
settings = get_settings()
logger = logging.getLogger(__name__)


async def _log_search(db: AsyncSession, user: User | None, q: str, model_used: str, results: list[dict]) -> None:
    # Logged on every call, cache hit or not - it's still a real search event, and the result
    # rows below need fresh ids for feedback to target even when the content came from cache.
    query_row = SearchQuery(
        user_id=user.id if user else None,
        query_text=q,
        model_used=model_used,
    )
    db.add(query_row)
    await db.flush()  # need query_row.id before creating the result rows below

    result_rows = [
        SearchResult(
            search_query_id=query_row.id,
            document_id=r["doc_id"],
            rank=rank,
            score=r["score"],
        )
        for rank, r in enumerate(results, start=1)
    ]
    db.add_all(result_rows)
    await db.commit()

    for r, row in zip(results, result_rows):
        r["search_result_id"] = row.id


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1),
    top_k: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_current_user),
) -> SearchResponse:
    cache_key = cache_service.make_key(q, top_k)
    results = await cache_service.get(cache_key)
    if results is None:
        results = await retrieval_service.search(db, q, top_k=top_k)
        await cache_service.set(cache_key, results)

    await _log_search(db, user, q, settings.embedding_model_name, results)
    return SearchResponse(query=q, results=results)


@router.get("/search/hybrid", response_model=SearchResponse)
async def search_hybrid(
    q: str = Query(..., min_length=1),
    top_k: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_current_user),
) -> SearchResponse:
    cache_key = cache_service.make_key(q, top_k, method="hybrid")
    results = await cache_service.get(cache_key)
    if results is None:
        results = await hybrid_search_service.search(db, q, top_k=top_k)
        await cache_service.set(cache_key, results)

    model_used = f"hybrid+rrf+{settings.cross_encoder_model_name}"
    await _log_search(db, user, q, model_used, results)
    return SearchResponse(query=q, results=results)


@router.post("/search/rag", response_model=RagResponse)
async def search_rag(body: RagRequest, db: AsyncSession = Depends(get_db)) -> RagResponse:
    if not settings.anthropic_api_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "AI answers aren't configured on this server")

    rows = await db.execute(
        select(SearchResult, Document)
        .join(Document, Document.id == SearchResult.document_id)
        .where(SearchResult.id.in_(body.search_result_ids))
    )
    by_id = {sr.id: (sr, doc) for sr, doc in rows.all()}
    missing = [str(rid) for rid in body.search_result_ids if rid not in by_id]
    if missing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown search_result_id(s): {', '.join(missing)}")

    # Preserve the caller's order (the frontend's own display order) - citation numbers are
    # positional against this list, not against rank/score, so the order given is the order used.
    ordered = [by_id[rid] for rid in body.search_result_ids]
    docs = [{"title": doc.title, "summary": doc.summary, "language": doc.language} for _, doc in ordered]

    try:
        answer = await rag_service.synthesize(body.query, docs)
    except Exception:
        logger.exception("RAG synthesis failed")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "AI answer is temporarily unavailable")

    citations = [
        RagCitation(number=n, search_result_id=ordered[n - 1][0].id, title=ordered[n - 1][1].title)
        for n in extract_cited_numbers(answer, len(docs))
    ]
    return RagResponse(answer=answer, citations=citations, model=settings.rag_model_name)
