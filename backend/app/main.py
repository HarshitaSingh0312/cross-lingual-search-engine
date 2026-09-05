from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import admin, auth, feedback, health, me, search
from app.db.base import async_session
from app.services.cache_service import cache_service
from app.services.hybrid_search import hybrid_search_service
from app.services.rag_service import rag_service
from app.services.retrieval_service import retrieval_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    retrieval_service.load()  # load the embedding model once, not per-request
    async with async_session() as db:
        await hybrid_search_service.load(db)  # builds the BM25 index, loads the cross-encoder
    yield
    await cache_service.close()
    await rag_service.close()


app = FastAPI(title="Cross-Lingual Search Engine", lifespan=lifespan)

app.include_router(health.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(feedback.router, prefix="/api/v1")
app.include_router(me.router, prefix="/api/v1")
