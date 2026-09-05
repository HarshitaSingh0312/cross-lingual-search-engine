from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.services.cache_service import cache_service
from app.services.hybrid_search import hybrid_search_service
from app.services.retrieval_service import retrieval_service

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    # Liveness only: "is the process up," never touches the DB/Redis/model - a dependency
    # blip shouldn't make an orchestrator (or UptimeRobot) think the whole process is dead.
    return {"status": "ok"}


@router.get("/ready")
async def ready(db: AsyncSession = Depends(get_db)) -> dict:
    # Readiness: "can this instance actually serve a search right now" - checks the things
    # a real /search request depends on. A load balancer should stop routing traffic here
    # if any of these are down, even though the process itself (health) is still alive.
    checks = {
        "model_loaded": retrieval_service.model is not None and hybrid_search_service.bm25 is not None,
        "redis": await cache_service.ping(),
    }
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False

    if all(checks.values()):
        return {"status": "ready", "checks": checks}
    raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail={"status": "not_ready", "checks": checks})
