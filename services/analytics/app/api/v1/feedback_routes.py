from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.core.security import get_current_user
from app.schemas import FeedbackCreate, FeedbackResponse
from app.services import FeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])


def _extract_user_id(claims: Dict[str, object]) -> int:
    for key in ("id_user", "sub", "id"):
        value = claims.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            break
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authenticated user identifier is missing or invalid",
    )


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def create_feedback(
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: Dict[str, object] = Depends(get_current_user),
) -> FeedbackResponse:
    user_id = _extract_user_id(current_user)
    service = FeedbackService(db)
    return service.create_feedback(user_id=user_id, payload=payload)


@router.get("/fields/{field_id}", response_model=List[FeedbackResponse])
def get_feedback_by_field(
    field_id: int,
    db: Session = Depends(get_db),
) -> List[FeedbackResponse]:
    service = FeedbackService(db)
    return service.get_feedback_by_field(field_id=field_id)


@router.delete("/{feedback_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_feedback(
    feedback_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, object] = Depends(get_current_user),
) -> Response:
    user_id = _extract_user_id(current_user)
    service = FeedbackService(db)
    service.delete_feedback(feedback_id=feedback_id, user_id=user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
