import uuid

from pydantic import BaseModel, Field


class RagRequest(BaseModel):
    query: str = Field(..., min_length=1)
    # The search_result_id's the frontend is already displaying - not a fresh query, so the
    # cited [n] numbers below line up with cards already on screen. Capped at 10 to bound
    # prompt size (and cost) regardless of what top_k the original search used.
    search_result_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=10)


class RagCitation(BaseModel):
    number: int
    search_result_id: uuid.UUID
    title: str


class RagResponse(BaseModel):
    answer: str
    citations: list[RagCitation]
    model: str
