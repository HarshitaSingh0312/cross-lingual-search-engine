import uuid

from pydantic import BaseModel


class FeedbackCreate(BaseModel):
    search_result_id: uuid.UUID
    is_relevant: bool


class FeedbackOut(BaseModel):
    id: uuid.UUID
    search_result_id: uuid.UUID
    is_relevant: bool

    model_config = {"from_attributes": True}
