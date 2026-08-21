from pydantic import BaseModel


class SearchResult(BaseModel):
    doc_id: str
    title: str
    summary: str
    language: str
    url: str | None
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
