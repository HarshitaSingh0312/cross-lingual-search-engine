import uuid
from datetime import datetime

from pydantic import BaseModel


class SearchHistoryItem(BaseModel):
    id: uuid.UUID
    query_text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BookmarkCreate(BaseModel):
    document_id: str


class BookmarkDocument(BaseModel):
    id: str
    title: str
    summary: str
    language: str
    url: str | None

    model_config = {"from_attributes": True}


class BookmarkOut(BaseModel):
    id: uuid.UUID
    document_id: str
    created_at: datetime
    document: BookmarkDocument

    model_config = {"from_attributes": True}
