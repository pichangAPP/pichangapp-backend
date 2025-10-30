"""Service layer that orchestrates chatbot analytics interactions."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from ..infrastructure.database import DatabaseError, get_connection
from ..models import FieldRecommendation
from ..repositories.analytics_repository import (
    ChatSessionRepository,
    ChatbotLogRepository,
    FeedbackRepository,
    IntentRepository,
    RecommendationRepository,
)


class ChatbotAnalyticsService:
    """Provides high level operations used by the custom actions."""

    def __init__(self, *, source_model: Optional[str] = None) -> None:
        self._source_model = source_model or os.getenv("RASA_SOURCE_MODEL")
        if not self._source_model:
            self._source_model = os.getenv("RASA_MODEL_NAME", "rasa-pro")

    # ------------------------------------------------------------------
    # Chat session helpers
    # ------------------------------------------------------------------
    def ensure_chat_session(
        self, user_id: int, theme: str, user_role: Optional[str]
    ) -> int:
        with get_connection() as connection:
            repository = ChatSessionRepository(connection)
            return repository.ensure_session(user_id=user_id, theme=theme, user_role=user_role)

    def close_chat_session(self, chatbot_id: int) -> None:
        with get_connection() as connection:
            repository = ChatSessionRepository(connection)
            repository.close_session(chatbot_id)

    # ------------------------------------------------------------------
    # Intent analytics helpers
    # ------------------------------------------------------------------
    def ensure_intent(
        self,
        *,
        intent_name: str,
        example_phrases: Sequence[str],
        response_template: str,
        confidence: Optional[float],
        detected: bool,
        false_positive: bool,
        source_model: Optional[str] = None,
    ) -> int:
        timestamp = datetime.now(timezone.utc)
        cleaned_examples = {
            phrase.strip()
            for phrase in example_phrases
            if phrase and phrase.strip()
        }

        with get_connection() as connection:
            repository = IntentRepository(connection)
            existing = repository.fetch_by_name(intent_name)

            normalized_confidence = None
            if confidence is not None:
                normalized_confidence = round(float(confidence), 4)

            if existing:
                existing_examples = existing.get("example_phrases") or ""
                example_set = {
                    line.strip()
                    for line in existing_examples.splitlines()
                    if line.strip()
                }
                example_set.update(cleaned_examples)
                examples_text = "\n".join(sorted(example_set))

                previous_total = int(existing.get("total_detected") or 0)
                previous_confidence = float(existing.get("confidence_avg") or 0.0)
                total_detected = previous_total

                if detected:
                    total_detected += 1

                confidence_avg = previous_confidence
                if detected and normalized_confidence is not None:
                    if previous_total <= 0:
                        confidence_avg = normalized_confidence
                    else:
                        confidence_avg = round(
                            (
                                (previous_confidence * previous_total)
                                + normalized_confidence
                            )
                            / (previous_total + 1),
                            4,
                        )

                false_positives_count = int(existing.get("false_positives") or 0)
                if false_positive:
                    false_positives_count += 1

                repository.update(
                    intent_id=int(existing["id_intent"]),
                    example_phrases=examples_text,
                    response_template=response_template,
                    confidence_avg=confidence_avg,
                    total_detected=total_detected,
                    false_positives=false_positives_count,
                    source_model=source_model or self._source_model,
                    last_detected=timestamp if detected else None,
                    updated_at=timestamp,
                )
                return int(existing["id_intent"])

            examples_text = "\n".join(sorted(cleaned_examples))
            return repository.create(
                intent_name=intent_name,
                example_phrases=examples_text,
                response_template=response_template,
                confidence_avg=normalized_confidence or 0.0,
                total_detected=1 if detected else 0,
                false_positives=1 if false_positive else 0,
                source_model=source_model or self._source_model,
                last_detected=timestamp if detected else None,
                created_at=timestamp,
                updated_at=timestamp,
            )

    # ------------------------------------------------------------------
    # Recommendation and log helpers
    # ------------------------------------------------------------------
    def create_recommendation_log(
        self,
        *,
        status: str,
        message: str,
        suggested_start: datetime,
        suggested_end: datetime,
        field_id: int,
        user_id: Optional[int],
    ) -> int:
        with get_connection() as connection:
            repository = RecommendationRepository(connection)
            return repository.create_log(
                status=status,
                message=message,
                suggested_start=suggested_start,
                suggested_end=suggested_end,
                field_id=field_id,
                user_id=user_id,
            )

    def log_chatbot_message(
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
        with get_connection() as connection:
            repository = ChatbotLogRepository(connection)
            repository.add_entry(
                session_id=session_id,
                intent_id=intent_id,
                recommendation_id=recommendation_id,
                message_text=message_text,
                bot_response=bot_response,
                response_type=response_type,
                sender_type=sender_type,
                user_id=user_id,
                intent_confidence=intent_confidence,
                metadata=metadata,
            )

    def fetch_recommendation_history(self, session_id: int, limit: int) -> List[Dict[str, Any]]:
        with get_connection() as connection:
            repository = RecommendationRepository(connection)
            return repository.fetch_history(session_id, limit)

    def fetch_field_recommendations(
        self,
        *,
        sport: Optional[str],
        surface: Optional[str],
        location: Optional[str],
        limit: int,
    ) -> List[FieldRecommendation]:
        with get_connection() as connection:
            repository = RecommendationRepository(connection)
            return repository.fetch_field_recommendations(
                sport=sport,
                surface=surface,
                location=location,
                limit=limit,
            )

    def fetch_feedback_for_user(self, user_id: int, limit: int) -> List[Dict[str, Any]]:
        with get_connection() as connection:
            repository = FeedbackRepository(connection)
            return repository.fetch_recent(user_id, limit)


chatbot_service = ChatbotAnalyticsService()

__all__ = ["ChatbotAnalyticsService", "DatabaseError", "chatbot_service"]
