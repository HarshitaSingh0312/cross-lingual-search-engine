from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_admin_user
from app.db.base import get_db
from app.db.models import SearchQuery, User
from app.schemas.auth import UserOut
from app.tasks.cache_tasks import warm_cache

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut], dependencies=[Depends(get_current_admin_user)])
async def list_users(db: AsyncSession = Depends(get_db)) -> list[User]:
    result = await db.scalars(select(User).order_by(User.created_at))
    return list(result)


@router.post(
    "/cache/warm-popular",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(get_current_admin_user)],
)
async def warm_popular_cache(
    background_tasks: BackgroundTasks,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Fast: only counts recent queries, from the search_queries table Phase 4 already logs
    # to. The slow part - re-running each one through the embedding model - happens after
    # this response is sent (see tasks/cache_tasks.warm_cache), so the admin isn't stuck
    # waiting on N sequential model calls just to kick this off.
    rows = await db.execute(
        select(SearchQuery.query_text, func.count().label("n"))
        .group_by(SearchQuery.query_text)
        .order_by(func.count().desc())
        .limit(limit)
    )
    queries = [row.query_text for row in rows]
    background_tasks.add_task(warm_cache, queries)
    return {"warming": queries}
