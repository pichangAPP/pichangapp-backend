from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Feedback


@dataclass(frozen=True)
class RentFeedbackContext:
    rent_id: int
    end_time: datetime
    field_id: int
    campus_id: int
    user_id: int


class FeedbackRepositoryError(RuntimeError):
    """Raised when feedback operations cannot be completed."""


def create_feedback(db: Session, feedback: Feedback) -> Feedback:
    try:
        db.add(feedback)
        db.flush([feedback])
    except SQLAlchemyError as exc:  # pragma: no cover - defensive
        raise FeedbackRepositoryError("Failed to persist feedback") from exc
    return feedback


def delete_feedback(db: Session, feedback: Feedback) -> None:
    try:
        db.delete(feedback)
        db.flush([feedback])
    except SQLAlchemyError as exc:  # pragma: no cover - defensive
        raise FeedbackRepositoryError("Failed to delete feedback") from exc


def get_feedback(db: Session, feedback_id: int) -> Optional[Feedback]:
    return db.query(Feedback).filter(Feedback.id_feedback == feedback_id).first()


def get_feedback_by_rent_and_user(db: Session, rent_id: int, user_id: int) -> Optional[Feedback]:
    return (
        db.query(Feedback)
        .filter(Feedback.id_rent == rent_id, Feedback.id_user == user_id)
        .first()
    )


def fetch_rent_context(db: Session, rent_id: int) -> Optional[RentFeedbackContext]:
    query = text(
        """
        SELECT
            rent.id_rent AS rent_id,
            rent.end_time AS end_time,
            schedule.id_field AS field_id,
            field.id_campus AS campus_id,
            schedule.id_user AS user_id
        FROM reservation.rent AS rent
        JOIN reservation.schedule AS schedule ON schedule.id_schedule = rent.id_schedule
        JOIN booking.field AS field ON field.id_field = schedule.id_field
        WHERE rent.id_rent = :rent_id
        LIMIT 1
        """
    )
    try:
        result = db.execute(query, {"rent_id": rent_id}).mappings().first()
    except SQLAlchemyError as exc:  # pragma: no cover - defensive
        raise FeedbackRepositoryError("Failed to fetch rent context") from exc
    if result is None:
        return None
    return RentFeedbackContext(
        rent_id=result["rent_id"],
        end_time=result["end_time"],
        field_id=result["field_id"],
        campus_id=result["campus_id"],
        user_id=result["user_id"],
    )


def list_feedback_by_field(db: Session, field_id: int) -> List[Dict[str, Any]]:
    query = text(
        """
        SELECT
            feedback.id_feedback,
            feedback.rating,
            feedback.comment,
            feedback.created_at,
            feedback.id_user,
            feedback.id_rent
        FROM analytics.feedback AS feedback
        JOIN reservation.rent AS rent ON rent.id_rent = feedback.id_rent
        JOIN reservation.schedule AS schedule ON schedule.id_schedule = rent.id_schedule
        WHERE schedule.id_field = :field_id
        ORDER BY feedback.created_at DESC
        """
    )
    try:
        rows = db.execute(query, {"field_id": field_id}).mappings().all()
    except SQLAlchemyError as exc:  # pragma: no cover - defensive
        raise FeedbackRepositoryError("Failed to list feedback for field") from exc
    payload: List[Dict[str, Any]] = []
    for row in rows:
        rating = row["rating"]
        payload.append(
            {
                "id_feedback": row["id_feedback"],
                "rating": float(rating) if rating is not None else None,
                "comment": row["comment"],
                "created_at": row["created_at"],
                "id_user": row["id_user"],
                "id_rent": row["id_rent"],
            }
        )
    return payload


def recalculate_campus_rating(db: Session, campus_id: int) -> None:
    rating_query = text(
        """
        SELECT AVG(feedback.rating) AS average_rating
        FROM analytics.feedback AS feedback
        JOIN reservation.rent AS rent ON rent.id_rent = feedback.id_rent
        JOIN reservation.schedule AS schedule ON schedule.id_schedule = rent.id_schedule
        JOIN booking.field AS field ON field.id_field = schedule.id_field
        WHERE feedback.rating IS NOT NULL
          AND field.id_campus = :campus_id
        """
    )
    try:
        avg_result = db.execute(rating_query, {"campus_id": campus_id}).scalar()
    except SQLAlchemyError as exc:  # pragma: no cover - defensive
        raise FeedbackRepositoryError("Failed to compute campus rating") from exc

    if avg_result is None:
        return

    if isinstance(avg_result, Decimal):
        average = avg_result
    else:
        average = Decimal(str(avg_result))

    normalized = average.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

    update_query = text(
        """
        UPDATE booking.campus
        SET rating = :rating
        WHERE id_campus = :campus_id
        """
    )
    try:
        db.execute(update_query, {"rating": normalized, "campus_id": campus_id})
        db.flush()
    except SQLAlchemyError as exc:  # pragma: no cover - defensive
        raise FeedbackRepositoryError("Failed to update campus rating") from exc


__all__ = [
    "FeedbackRepositoryError",
    "RentFeedbackContext",
    "create_feedback",
    "delete_feedback",
    "fetch_rent_context",
    "get_feedback",
    "get_feedback_by_rent_and_user",
    "list_feedback_by_field",
    "recalculate_campus_rating",
]
