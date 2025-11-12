from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Feedback
from app.repository import (
    FeedbackRepositoryError,
    RentFeedbackContext,
    create_feedback,
    delete_feedback,
    fetch_rent_context,
    get_feedback,
    get_feedback_by_rent_and_user,
    list_feedback_by_field,
    recalculate_campus_rating,
)
from app.schemas import FeedbackCreate, FeedbackResponse


class FeedbackService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create_feedback(self, *, user_id: int, payload: FeedbackCreate) -> FeedbackResponse:
        rent_context = self._get_rent_context(payload.id_rent)

        if rent_context.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the renter can submit feedback for this booking",
            )

        finished_at = self._ensure_timezone(rent_context.end_time)
        if finished_at > datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Feedback can only be submitted after the rent has finished",
            )

        existing = get_feedback_by_rent_and_user(self._db, payload.id_rent, user_id)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Feedback has already been submitted for this rent",
            )

        feedback = Feedback(
            rating=payload.rating,
            comment=payload.comment,
            id_user=user_id,
            id_rent=payload.id_rent,
        )

        try:
            create_feedback(self._db, feedback)
            if payload.rating is not None:
                recalculate_campus_rating(self._db, rent_context.campus_id)
            self._db.commit()
        except FeedbackRepositoryError as exc:
            self._db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc

        self._db.refresh(feedback)
        return self._map_model_to_response(feedback)

    def get_feedback_by_field(self, field_id: int) -> List[FeedbackResponse]:
        try:
            rows = list_feedback_by_field(self._db, field_id)
        except FeedbackRepositoryError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc

        responses: List[FeedbackResponse] = []
        for row in rows:
            responses.append(
                FeedbackResponse(
                    id_feedback=row["id_feedback"],
                    rating=row["rating"],
                    comment=row["comment"],
                    created_at=row["created_at"],
                    id_user=row["id_user"],
                    id_rent=row["id_rent"],
                )
            )
        return responses

    def delete_feedback(self, *, feedback_id: int, user_id: int) -> None:
        feedback = get_feedback(self._db, feedback_id)
        if feedback is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feedback not found",
            )

        if feedback.id_user != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to delete this feedback",
            )

        rent_context = self._get_rent_context(feedback.id_rent)

        try:
            delete_feedback(self._db, feedback)
            recalculate_campus_rating(self._db, rent_context.campus_id)
            self._db.commit()
        except FeedbackRepositoryError as exc:
            self._db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc

    def _get_rent_context(self, rent_id: int) -> RentFeedbackContext:
        context = fetch_rent_context(self._db, rent_id)
        if context is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rent not found for feedback processing",
            )
        return context

    @staticmethod
    def _ensure_timezone(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _map_model_to_response(feedback: Feedback) -> FeedbackResponse:
        rating = float(feedback.rating) if feedback.rating is not None else None
        return FeedbackResponse(
            id_feedback=feedback.id_feedback,
            rating=rating,
            comment=feedback.comment,
            created_at=feedback.created_at,
            id_user=feedback.id_user,
            id_rent=feedback.id_rent,
        )


__all__ = ["FeedbackService"]
