from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import get_current_user
from app.db.base import get_db
from app.db.models import Bookmark, Document, SearchQuery, User
from app.schemas.me import BookmarkCreate, BookmarkOut, SearchHistoryItem

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/history", response_model=list[SearchHistoryItem])
async def get_history(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SearchQuery]:
    result = await db.scalars(
        select(SearchQuery)
        .where(SearchQuery.user_id == user.id)
        .order_by(SearchQuery.created_at.desc())
        .limit(limit)
    )
    return list(result)


@router.post("/bookmarks", response_model=BookmarkOut, status_code=status.HTTP_201_CREATED)
async def create_bookmark(
    body: BookmarkCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Bookmark:
    document = await db.get(Document, body.document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    existing = await db.scalar(
        select(Bookmark)
        .where(Bookmark.user_id == user.id, Bookmark.document_id == body.document_id)
        .options(selectinload(Bookmark.document))
    )
    if existing is not None:
        return existing  # bookmarking twice is a no-op, not an error

    bookmark = Bookmark(user_id=user.id, document_id=body.document_id)
    db.add(bookmark)
    await db.commit()
    await db.refresh(bookmark, attribute_names=["document"])
    return bookmark


@router.get("/bookmarks", response_model=list[BookmarkOut])
async def list_bookmarks(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Bookmark]:
    result = await db.scalars(
        select(Bookmark)
        .where(Bookmark.user_id == user.id)
        .order_by(Bookmark.created_at.desc())
        .options(selectinload(Bookmark.document))
    )
    return list(result)
