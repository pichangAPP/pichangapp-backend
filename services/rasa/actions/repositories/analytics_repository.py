"""Repositories that encapsulate database access for analytics tables."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..db_models import (
    Campus,
    Chatbot,
    ChatbotLog,
    Feedback,
    Field,
    Intent,
    RecommendationLog,
    Sport,
)
from ..infrastructure.database import DatabaseError
from ..models import FieldRecommendation

LOGGER = logging.getLogger(__name__)


def _normalize_decimal(value: Optional[Decimal | float]) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _format_time(value: Optional[datetime | Any]) -> str:
    if value is None:
        return ""
    try:
        return value.strftime("%H:%M:%S")
    except AttributeError:
        return str(value)


class ChatSessionRepository:
    """Persistence helpers for the analytics.chatbot table."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def ensure_session(
        self,
        *,
        user_id: int,
        theme: str,
        user_role: Optional[str] = None,
    ) -> int:
        del user_role  # Role is no longer persisted in analytics.chatbot
        LOGGER.info(
            "[ChatSessionRepository] ensuring session for user_id=%s theme=%s",
            user_id,
            theme,
        )
        try:
            stmt = (
                select(Chatbot)
                .where(Chatbot.id_user == user_id)
                .order_by(Chatbot.started_at.desc())
                .limit(1)
            )
            existing = self._db.execute(stmt).scalars().first()
        except SQLAlchemyError as exc:
            raise DatabaseError(str(exc)) from exc

        if existing:
            existing.status = "active"
            existing.ended_at = None
            try:
                self._db.flush()
            except SQLAlchemyError as exc:
                raise DatabaseError(str(exc)) from exc
            LOGGER.debug(
                "[ChatSessionRepository] reactivated session id=%s for user_id=%s",
                existing.id_chatbot,
                user_id,
            )
            return int(existing.id_chatbot)

        chat_session = Chatbot(theme=theme, status="active", id_user=user_id)
        self._db.add(chat_session)
        try:
            self._db.flush()
        except SQLAlchemyError as exc:
            raise DatabaseError(str(exc)) from exc

        LOGGER.info(
            "[ChatSessionRepository] created new session id=%s for user_id=%s",
            chat_session.id_chatbot,
            user_id,
        )
        return int(chat_session.id_chatbot)

    def close_session(self, chatbot_id: int) -> None:
        LOGGER.info(
            "[ChatSessionRepository] closing session id=%s",
            chatbot_id,
        )
        try:
            session = self._db.get(Chatbot, chatbot_id)
        except SQLAlchemyError as exc:
            raise DatabaseError(str(exc)) from exc

        if session is None:
            LOGGER.warning(
                "[ChatSessionRepository] attempted to close missing session id=%s",
                chatbot_id,
            )
            return

        session.ended_at = datetime.now(timezone.utc)
        session.status = "closed"
        try:
            self._db.flush()
        except SQLAlchemyError as exc:
            raise DatabaseError(str(exc)) from exc


class IntentRepository:
    """Persistence helpers for analytics.intents."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def fetch_by_name(self, intent_name: str) -> Optional[Dict[str, Any]]:
        LOGGER.debug(
            "[IntentRepository] fetch_by_name intent=%s",
            intent_name,
        )
        try:
            stmt = select(Intent).where(Intent.intent_name == intent_name).limit(1)
            intent = self._db.execute(stmt).scalars().first()
        except SQLAlchemyError as exc:
            raise DatabaseError(str(exc)) from exc

        if not intent:
            return None

        return {
            "id_intent": intent.id_intent,
            "intent_name": intent.intent_name,
            "example_phrases": intent.example_phrases,
            "response_template": intent.response_template,
            "confidence_avg": _normalize_decimal(intent.confidence_avg),
            "total_detected": intent.total_detected,
            "false_positives": intent.false_positives,
            "source_model": intent.source_model,
            "last_detected": intent.last_detected,
            "created_at": intent.created_at,
            "updated_at": intent.updated_at,
        }

    def update(
        self,
        *,
        intent_id: int,
        example_phrases: str,
        response_template: str,
        confidence_avg: Optional[float],
        total_detected: int,
        false_positives: int,
        source_model: str,
        last_detected: Optional[datetime],
        updated_at: datetime,
    ) -> None:
        LOGGER.info(
            "[IntentRepository] update intent_id=%s total_detected=%s false_positives=%s",
            intent_id,
            total_detected,
            false_positives,
        )
        try:
            intent = self._db.get(Intent, intent_id)
        except SQLAlchemyError as exc:
            raise DatabaseError(str(exc)) from exc

        if intent is None:
            raise DatabaseError(f"Intent with id {intent_id} not found")

        intent.example_phrases = example_phrases
        intent.response_template = response_template
        intent.confidence_avg = confidence_avg
        intent.total_detected = total_detected
        intent.false_positives = false_positives
        intent.source_model = source_model
        if last_detected is not None:
            intent.last_detected = last_detected
        intent.updated_at = updated_at

        try:
            self._db.flush()
        except SQLAlchemyError as exc:
            raise DatabaseError(str(exc)) from exc

    def create(
        self,
        *,
        intent_name: str,
        example_phrases: str,
        response_template: str,
        confidence_avg: float,
        total_detected: int,
        false_positives: int,
        source_model: str,
        last_detected: Optional[datetime],
        created_at: datetime,
        updated_at: datetime,
    ) -> int:
        LOGGER.info(
            "[IntentRepository] create intent_name=%s detected=%s",
            intent_name,
            total_detected,
        )
        intent = Intent(
            intent_name=intent_name,
            example_phrases=example_phrases,
            response_template=response_template,
            confidence_avg=confidence_avg,
            total_detected=total_detected,
            false_positives=false_positives,
            source_model=source_model,
            last_detected=last_detected,
            created_at=created_at,
            updated_at=updated_at,
        )
        self._db.add(intent)
        try:
            self._db.flush()
        except SQLAlchemyError as exc:
            raise DatabaseError(str(exc)) from exc
        return int(intent.id_intent)


class RecommendationRepository:
    """Persistence helpers for recomendation_log and related lookups."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create_log(
        self,
        *,
        status: str,
        message: str,
        suggested_start: datetime,
        suggested_end: datetime,
        field_id: int,
        user_id: Optional[int],
    ) -> int:
        LOGGER.info(
            "[RecommendationRepository] create_log status=%s field_id=%s user_id=%s",
            status,
            field_id,
            user_id,
        )
        recommendation = RecommendationLog(
            status=status,
            message=message,
            suggested_time_start=suggested_start,
            suggested_time_end=suggested_end,
            id_field=field_id,
            id_user=user_id,
        )
        self._db.add(recommendation)
        try:
            self._db.flush()
        except SQLAlchemyError as exc:
            raise DatabaseError(str(exc)) from exc
        LOGGER.info(
            "[RecommendationRepository] created log id=%s",
            recommendation.id_recommendation_log,
        )
        return int(recommendation.id_recommendation_log)

    def fetch_history(self, session_id: int, limit: int) -> List[Dict[str, Any]]:
        LOGGER.debug(
            "[RecommendationRepository] fetch_history session_id=%s limit=%s",
            session_id,
            limit,
        )
        try:
            stmt = (
                select(
                    RecommendationLog.timestamp,
                    RecommendationLog.status,
                    RecommendationLog.message,
                    RecommendationLog.suggested_time_start,
                    RecommendationLog.suggested_time_end,
                    Field.field_name,
                    Sport.sport_name,
                    Campus.name.label("campus_name"),
                )
                .join(
                    ChatbotLog,
                    ChatbotLog.id_recommendation_log
                    == RecommendationLog.id_recommendation_log,
                )
                .join(Field, RecommendationLog.id_field == Field.id_field)
                .join(Sport, Field.id_sport == Sport.id_sport)
                .join(Campus, Field.id_campus == Campus.id_campus)
                .where(ChatbotLog.id_chatbot == session_id)
                .order_by(RecommendationLog.timestamp.desc())
                .limit(limit)
            )
            result = self._db.execute(stmt).all()
        except SQLAlchemyError as exc:
            raise DatabaseError(str(exc)) from exc

        history: List[Dict[str, Any]] = []
        for row in result:
            history.append(
                {
                    "timestamp": row.timestamp,
                    "status": row.status,
                    "message": row.message,
                    "suggested_time_start": row.suggested_time_start,
                    "suggested_time_end": row.suggested_time_end,
                    "field_name": row.field_name,
                    "sport_name": row.sport_name,
                    "campus_name": row.campus_name,
                }
            )
        return history

    def fetch_field_recommendations(
        self,
        *,
        sport: Optional[str],
        surface: Optional[str],
        location: Optional[str],
        limit: int,
    ) -> List[FieldRecommendation]:
        LOGGER.debug(
            "[RecommendationRepository] fetch_field_recommendations sport=%s surface=%s location=%s limit=%s",
            sport,
            surface,
            location,
            limit,
        )
        try:
            stmt = (
                select(
                    Field.id_field,
                    Field.field_name,
                    Field.surface,
                    Field.capacity,
                    Field.price_per_hour,
                    Field.open_time,
                    Field.close_time,
                    Sport.sport_name,
                    Campus.name.label("campus_name"),
                    Campus.district,
                    Campus.address,
                )
                .join(Sport, Field.id_sport == Sport.id_sport)
                .join(Campus, Field.id_campus == Campus.id_campus)
            )
            if sport:
                stmt = stmt.where(Sport.sport_name.ilike(f"%{sport}%"))
            if surface:
                stmt = stmt.where(Field.surface.ilike(f"%{surface}%"))
            if location:
                pattern = f"%{location}%"
                stmt = stmt.where(
                    (Campus.district.ilike(pattern))
                    | (Campus.address.ilike(pattern))
                    | (Campus.name.ilike(pattern))
                )
            stmt = stmt.order_by(Field.price_per_hour.asc(), Field.capacity.desc()).limit(limit)
            rows = self._db.execute(stmt).all()
        except SQLAlchemyError as exc:
            raise DatabaseError(str(exc)) from exc

        recommendations: List[FieldRecommendation] = []
        for row in rows:
            recommendations.append(
                FieldRecommendation(
                    id_field=int(row.id_field),
                    field_name=row.field_name,
                    sport_name=row.sport_name,
                    campus_name=row.campus_name,
                    district=row.district or "",
                    address=row.address or "",
                    surface=row.surface or "",
                    capacity=int(row.capacity) if row.capacity is not None else 0,
                    price_per_hour=_normalize_decimal(row.price_per_hour) or 0.0,
                    open_time=_format_time(row.open_time),
                    close_time=_format_time(row.close_time),
                )
            )
        return recommendations


class ChatbotLogRepository:
    """Persistence helpers for analytics.chatbot_log."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def add_entry(
        self,
        *,
        session_id: int,
        intent_id: Optional[int],
        recommendation_id: Optional[int],
        message_text: str,
        bot_response: str,
        response_type: str,
        sender_type: str,
        user_id: Optional[int],
        intent_confidence: Optional[float],
        metadata: Optional[Dict[str, Any]],
        ) -> ChatbotLog:
        """Insert a new chatbot log entry."""
        LOGGER.info(
            "[ChatbotLogRepository] add_entry session_id=%s response_type=%s sender=%s intent_id=%s recommendation_id=%s",
            session_id,
            response_type,
            sender_type,
            intent_id,
            recommendation_id,
        )
        message_value = "" if message_text is None else str(message_text)
        bot_response_value = "" if bot_response is None else str(bot_response)
        rounded_confidence = (
            round(float(intent_confidence), 4)
            if intent_confidence is not None
            else None
        )
        entry = ChatbotLog(
            id_chatbot=session_id,
            id_intent=intent_id,
            id_recommendation_log=recommendation_id,
            message=message_value,
            bot_response=bot_response_value,
            response_type=response_type,
            sender_type=sender_type,
            id_user=user_id,
            intent_detected=intent_id,
            intent_confidence=rounded_confidence,
            metadata_json=json.dumps(metadata, default=str) if metadata else None,
        )
        self._db.add(entry)
        try:
            self._db.flush()
            LOGGER.info("[ChatbotLogRepository] entry inserted id=%s", entry.id_chatbot_log)
            return entry
        except SQLAlchemyError as exc:
            LOGGER.error("[ChatbotLogRepository] DB error: %s", exc)
            raise DatabaseError(str(exc)) from exc


class FeedbackRepository:
    """Persistence helpers for analytics.feedback."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def fetch_recent(self, user_id: int, limit: int) -> List[Dict[str, Any]]:
        LOGGER.debug(
            "[FeedbackRepository] fetch_recent user_id=%s limit=%s",
            user_id,
            limit,
        )
        try:
            stmt = (
                select(
                    Feedback.rating,
                    Feedback.comment,
                    Feedback.created_at,
                    Feedback.id_rent,
                )
                .where(Feedback.id_user == user_id)
                .order_by(Feedback.created_at.desc())
                .limit(limit)
            )
            rows = self._db.execute(stmt).all()
        except SQLAlchemyError as exc:
            raise DatabaseError(str(exc)) from exc

        return [
            {
                "rating": row.rating,
                "comment": row.comment,
                "created_at": row.created_at,
                "id_rent": row.id_rent,
            }
            for row in rows
        ]


__all__ = [
    "ChatSessionRepository",
    "IntentRepository",
    "RecommendationRepository",
    "ChatbotLogRepository",
    "FeedbackRepository",
]
