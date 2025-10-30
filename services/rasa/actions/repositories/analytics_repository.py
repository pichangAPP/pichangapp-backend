"""Repositories that encapsulate database access for analytics tables."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from ..infrastructure.database import DatabaseError
from ..models import FieldRecommendation

LOGGER = logging.getLogger(__name__)


class ChatSessionRepository:
    """Persistence helpers for the analytics.chatbot table."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def ensure_session(
        self,
        *,
        user_id: int,
        theme: str,
        user_role: Optional[str],
    ) -> int:
        LOGGER.info(
            "[ChatSessionRepository] ensuring session for user_id=%s theme=%s role=%s",
            user_id,
            theme,
            user_role,
        )
        existing = self._connection.execute(
            text(
                """
                SELECT id_chatbot
                FROM analytics.chatbot
                WHERE id_user = :user_id
                ORDER BY started_at DESC
                LIMIT 1
                """
            ),
            {"user_id": user_id},
        ).scalar_one_or_none()

        if existing:
            LOGGER.debug(
                "[ChatSessionRepository] found existing session id=%s for user_id=%s",
                existing,
                user_id,
            )
            params: Dict[str, Any] = {"chatbot_id": existing}
            update_sql = text(
                """
                UPDATE analytics.chatbot
                SET status = 'active', ended_at = NULL
                WHERE id_chatbot = :chatbot_id
                """
            )

            if user_role:
                try:
                    self._connection.execute(
                        text(
                            """
                            UPDATE analytics.chatbot
                            SET status = 'active', ended_at = NULL, user_role = :user_role
                            WHERE id_chatbot = :chatbot_id
                            """
                        ),
                        {**params, "user_role": user_role},
                    )
                    LOGGER.debug(
                        "[ChatSessionRepository] refreshed role for session id=%s",
                        existing,
                    )
                    return int(existing)
                except SQLAlchemyError as exc:
                    if "user_role" not in str(exc).lower():
                        raise DatabaseError(str(exc)) from exc

            self._connection.execute(update_sql, params)
            LOGGER.debug(
                "[ChatSessionRepository] reactivated session id=%s",
                existing,
            )
            return int(existing)

        payload: Dict[str, Any] = {
            "theme": theme,
            "status": "active",
            "user_id": user_id,
        }

        columns = ["theme", "status", "id_user"]
        values = [":theme", ":status", ":user_id"]

        if user_role:
            columns.append("user_role")
            values.append(":user_role")
            payload["user_role"] = user_role

        insert_sql = text(
            f"""
            INSERT INTO analytics.chatbot ({', '.join(columns)})
            VALUES ({', '.join(values)})
            RETURNING id_chatbot
            """
        )

        try:
            created = self._connection.execute(insert_sql, payload).scalar_one()
            LOGGER.info(
                "[ChatSessionRepository] created new session id=%s for user_id=%s",
                created,
                user_id,
            )
            return int(created)
        except SQLAlchemyError as exc:
            if user_role and "user_role" in str(exc).lower():
                fallback_sql = text(
                    """
                    INSERT INTO analytics.chatbot (theme, status, id_user)
                    VALUES (:theme, :status, :user_id)
                    RETURNING id_chatbot
                    """
                )
                created = self._connection.execute(fallback_sql, payload).scalar_one()
                LOGGER.warning(
                    "[ChatSessionRepository] inserted session without role id=%s due to error=%s",
                    created,
                    exc,
                )
                return int(created)
            raise DatabaseError(str(exc)) from exc

    def close_session(self, chatbot_id: int) -> None:
        LOGGER.info(
            "[ChatSessionRepository] closing session id=%s",
            chatbot_id,
        )
        self._connection.execute(
            text(
                """
                UPDATE analytics.chatbot
                SET ended_at = now(), status = 'closed'
                WHERE id_chatbot = :chatbot_id
                """
            ),
            {"chatbot_id": chatbot_id},
        )


class IntentRepository:
    """Persistence helpers for analytics.intents."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def fetch_by_name(self, intent_name: str) -> Optional[Dict[str, Any]]:
        LOGGER.debug(
            "[IntentRepository] fetch_by_name intent=%s",
            intent_name,
        )
        result = self._connection.execute(
            text(
                """
                SELECT id_intent, example_phrases, total_detected, confidence_avg, false_positives
                FROM analytics.intents
                WHERE intent_name = :intent_name
                LIMIT 1
                """
            ),
            {"intent_name": intent_name},
        ).mappings().first()
        return dict(result) if result else None

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
        params = {
            "examples": example_phrases,
            "response_template": response_template,
            "confidence_avg": confidence_avg,
            "total_detected": total_detected,
            "false_positives": false_positives,
            "source_model": source_model,
            "last_detected": last_detected,
            "updated_at": updated_at,
            "id_intent": intent_id,
        }

        LOGGER.info(
            "[IntentRepository] update intent_id=%s total_detected=%s false_positives=%s",
            intent_id,
            total_detected,
            false_positives,
        )

        self._connection.execute(
            text(
                """
                UPDATE analytics.intents
                SET example_phrases = :examples,
                    response_template = :response_template,
                    confidence_avg = :confidence_avg,
                    total_detected = :total_detected,
                    false_positives = :false_positives,
                    source_model = :source_model,
                    last_detected = COALESCE(:last_detected, last_detected),
                    updated_at = :updated_at
                WHERE id_intent = :id_intent
                """
            ),
            params,
        )

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
        params = {
            "intent_name": intent_name,
            "examples": example_phrases,
            "response_template": response_template,
            "confidence_avg": confidence_avg,
            "total_detected": total_detected,
            "false_positives": false_positives,
            "source_model": source_model,
            "last_detected": last_detected,
            "created_at": created_at,
            "updated_at": updated_at,
        }

        LOGGER.info(
            "[IntentRepository] create intent_name=%s detected=%s",
            intent_name,
            total_detected,
        )

        created = self._connection.execute(
            text(
                """
                INSERT INTO analytics.intents (
                    intent_name,
                    example_phrases,
                    response_template,
                    confidence_avg,
                    total_detected,
                    false_positives,
                    source_model,
                    last_detected,
                    created_at,
                    updated_at
                )
                VALUES (
                    :intent_name,
                    :examples,
                    :response_template,
                    :confidence_avg,
                    :total_detected,
                    :false_positives,
                    :source_model,
                    :last_detected,
                    :created_at,
                    :updated_at
                )
                RETURNING id_intent
                """
            ),
            params,
        ).scalar_one()
        return int(created)


class RecommendationRepository:
    """Persistence helpers for recomendation_log and related lookups."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

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
        base_params = {
            "status": status,
            "message": message,
            "start": suggested_start,
            "end": suggested_end,
            "field_id": field_id,
        }

        columns = [
            "status",
            "message",
            "suggested_time_start",
            "suggested_time_end",
            "id_field",
        ]
        values = [":status", ":message", ":start", ":end", ":field_id"]

        if user_id is not None:
            columns.append("id_user")
            values.append(":user_id")
            base_params["user_id"] = user_id

        LOGGER.info(
            "[RecommendationRepository] create_log status=%s field_id=%s user_id=%s",
            status,
            field_id,
            user_id,
        )

        sql = text(
            f"""
            INSERT INTO analytics.recomendation_log ({', '.join(columns)})
            VALUES ({', '.join(values)})
            RETURNING id_recommendation_log
            """
        )

        try:
            created = self._connection.execute(sql, base_params).scalar_one()
            LOGGER.info(
                "[RecommendationRepository] created log id=%s",
                created,
            )
            return int(created)
        except SQLAlchemyError as exc:
            if user_id is not None and "id_user" in str(exc).lower():
                fallback_sql = text(
                    """
                    INSERT INTO analytics.recomendation_log (
                        status, message, suggested_time_start, suggested_time_end, id_field
                    )
                    VALUES (:status, :message, :start, :end, :field_id)
                    RETURNING id_recommendation_log
                    """
                )
                created = self._connection.execute(fallback_sql, base_params).scalar_one()
                LOGGER.warning(
                    "[RecommendationRepository] fallback insert without user for field_id=%s error=%s",
                    field_id,
                    exc,
                )
                return int(created)
            raise DatabaseError(str(exc)) from exc

    def fetch_history(self, session_id: int, limit: int) -> List[Dict[str, Any]]:
        LOGGER.debug(
            "[RecommendationRepository] fetch_history session_id=%s limit=%s",
            session_id,
            limit,
        )
        result = self._connection.execute(
            text(
                """
                SELECT
                    r.timestamp,
                    r.status,
                    r.message,
                    r.suggested_time_start,
                    r.suggested_time_end,
                    f.field_name,
                    s.sport_name,
                    c.name AS campus_name
                FROM analytics.chatbot_log AS cl
                JOIN analytics.recomendation_log AS r
                    ON cl.id_recommendation_log = r.id_recommendation_log
                JOIN booking.field AS f ON r.id_field = f.id_field
                JOIN booking.sports AS s ON f.id_sport = s.id_sport
                JOIN booking.campus AS c ON f.id_campus = c.id_campus
                WHERE cl.id_chatbot = :session_id
                ORDER BY r.timestamp DESC
                LIMIT :limit
                """
            ),
            {"session_id": session_id, "limit": limit},
        )
        return [dict(row) for row in result.mappings()]

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
        result = self._connection.execute(
            text(
                """
                SELECT
                    f.id_field,
                    f.field_name,
                    f.surface,
                    f.capacity,
                    f.price_per_hour,
                    f.open_time,
                    f.close_time,
                    s.sport_name,
                    c.name AS campus_name,
                    c.district,
                    c.address
                FROM booking.field AS f
                JOIN booking.sports AS s ON f.id_sport = s.id_sport
                JOIN booking.campus AS c ON f.id_campus = c.id_campus
                WHERE (:sport IS NULL OR s.sport_name ILIKE :sport_like)
                  AND (:surface IS NULL OR f.surface ILIKE :surface_like)
                  AND (
                    :location IS NULL
                    OR c.district ILIKE :location_like
                    OR c.address ILIKE :location_like
                    OR c.name ILIKE :location_like
                  )
                ORDER BY f.price_per_hour ASC, f.capacity DESC
                LIMIT :limit
                """
            ),
            {
                "sport": sport,
                "surface": surface,
                "location": location,
                "sport_like": f"%{sport}%" if sport else None,
                "surface_like": f"%{surface}%" if surface else None,
                "location_like": f"%{location}%" if location else None,
                "limit": limit,
            },
        )

        recommendations: List[FieldRecommendation] = []
        for row in result.mappings():
            recommendations.append(
                FieldRecommendation(
                    id_field=int(row["id_field"]),
                    field_name=row["field_name"],
                    sport_name=row["sport_name"],
                    campus_name=row["campus_name"],
                    district=row["district"],
                    address=row["address"],
                    surface=row["surface"],
                    capacity=int(row["capacity"]),
                    price_per_hour=float(row["price_per_hour"]),
                    open_time=str(row["open_time"]),
                    close_time=str(row["close_time"]),
                )
            )
        return recommendations


class ChatbotLogRepository:
    """Persistence helpers for analytics.chatbot_log."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

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
    ) -> None:
        base_columns = [
            "message",
            "response_type",
            "bot_response",
            "intent_detected",
            "sender_type",
            "id_chatbot",
            "id_intent",
            "id_recommendation_log",
        ]
        base_values: Dict[str, Any] = {
            "message": message_text,
            "response_type": response_type,
            "bot_response": bot_response,
            "intent_detected": intent_id or None,
            "sender_type": sender_type,
            "id_chatbot": session_id,
            "id_intent": intent_id or None,
            "id_recommendation_log": recommendation_id or None,
        }

        columns = list(base_columns)
        params = dict(base_values)

        if user_id is not None:
            columns.append("id_user")
            params["id_user"] = user_id

        if intent_confidence is not None:
            columns.append("intent_confidence")
            params["intent_confidence"] = round(float(intent_confidence), 4)

        if metadata:
            columns.append("metadata")
            params["metadata"] = json.dumps(metadata, default=str)

        placeholders = ", ".join(f":{key}" for key in params.keys())
        sql = text(
            f"""
            INSERT INTO analytics.chatbot_log ({', '.join(columns)})
            VALUES ({placeholders})
            """
        )

        LOGGER.info(
            "[ChatbotLogRepository] add_entry session_id=%s response_type=%s sender=%s intent_id=%s recommendation_id=%s",
            session_id,
            response_type,
            sender_type,
            intent_id,
            recommendation_id,
        )

        try:
            self._connection.execute(sql, params)
            LOGGER.debug(
                "[ChatbotLogRepository] entry inserted for session_id=%s",
                session_id,
            )
        except SQLAlchemyError as exc:
            if any(
                keyword in str(exc).lower()
                for keyword in ("intent_confidence", "metadata", "id_user")
            ):
                fallback_sql = text(
                    """
                    INSERT INTO analytics.chatbot_log (
                        message,
                        response_type,
                        bot_response,
                        intent_detected,
                        sender_type,
                        id_chatbot,
                        id_intent,
                        id_recommendation_log
                    )
                    VALUES (
                        :message,
                        :response_type,
                        :bot_response,
                        :intent_detected,
                        :sender_type,
                        :id_chatbot,
                        :id_intent,
                        :id_recommendation_log
                    )
                    """
                )
                self._connection.execute(fallback_sql, base_values)
                LOGGER.warning(
                    "[ChatbotLogRepository] fallback insert without optional columns for session_id=%s error=%s",
                    session_id,
                    exc,
                )
                return
            raise DatabaseError(str(exc)) from exc


class FeedbackRepository:
    """Persistence helpers for analytics.feedback."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def fetch_recent(self, user_id: int, limit: int) -> List[Dict[str, Any]]:
        LOGGER.debug(
            "[FeedbackRepository] fetch_recent user_id=%s limit=%s",
            user_id,
            limit,
        )
        result = self._connection.execute(
            text(
                """
                SELECT rating, comment, created_at, id_rent
                FROM analytics.feedback
                WHERE id_user = :user_id
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"user_id": user_id, "limit": limit},
        )
        return [dict(row) for row in result.mappings()]


__all__ = [
    "ChatSessionRepository",
    "IntentRepository",
    "RecommendationRepository",
    "ChatbotLogRepository",
    "FeedbackRepository",
]
