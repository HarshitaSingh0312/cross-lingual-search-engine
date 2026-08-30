import uuid

from pydantic import BaseModel


class SearchResult(BaseModel):
    doc_id: str
    title: str
    summary: str
    language: str
    url: str | None
    score: float
    # Row id of this result's logged occurrence - what POST /feedback is submitted against,
    # since the same document can appear in many searches with a different rank/score each time.
    search_result_id: uuid.UUID


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
