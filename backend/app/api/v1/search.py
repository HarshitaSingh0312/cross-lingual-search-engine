from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.schemas.search import SearchResponse
from app.services.retrieval_service import retrieval_service

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1),
    top_k: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    results = await retrieval_service.search(db, q, top_k=top_k)
    return SearchResponse(query=q, results=results)
