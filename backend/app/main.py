from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import admin, auth, health, search
from app.services.retrieval_service import retrieval_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    retrieval_service.load()  # load the embedding model once, not per-request
    yield


app = FastAPI(title="Cross-Lingual Search Engine", lifespan=lifespan)

app.include_router(health.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
