from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_optional_current_user
from app.db.base import get_db
from app.db.models import Feedback, SearchResult, User
from app.schemas.feedback import FeedbackCreate, FeedbackOut

router = APIRouter(tags=["feedback"])


@router.post("/feedback", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    body: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_current_user),
) -> Feedback:
    result = await db.get(SearchResult, body.search_result_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search result not found")

    feedback = None
    if user is not None:
        # Only logged-in votes can be deduped/updated - an anonymous vote has no identity
        # to match against, so every anonymous submission just inserts a new row.
        feedback = await db.scalar(
            select(Feedback).where(
                Feedback.search_result_id == body.search_result_id,
                Feedback.user_id == user.id,
            )
        )

    if feedback is not None:
        feedback.is_relevant = body.is_relevant
    else:
        feedback = Feedback(
            search_result_id=body.search_result_id,
            user_id=user.id if user else None,
            is_relevant=body.is_relevant,
        )
        db.add(feedback)

    await db.commit()
    await db.refresh(feedback)
    return feedback
