from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_optional_current_user
from app.core.config import get_settings
from app.db.base import get_db
from app.db.models import SearchQuery, SearchResult, User
from app.schemas.search import SearchResponse
from app.services.retrieval_service import retrieval_service

router = APIRouter(tags=["search"])
settings = get_settings()


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1),
    top_k: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_current_user),
) -> SearchResponse:
    results = await retrieval_service.search(db, q, top_k=top_k)

    # Logged here (not in retrieval_service) so the service stays pure retrieval logic -
    # history/feedback are a request-handling concern, not something a search call itself needs.
    query_row = SearchQuery(
        user_id=user.id if user else None,
        query_text=q,
        model_used=settings.embedding_model_name,
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

    return SearchResponse(query=q, results=results)
