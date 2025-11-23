"""Service layer that orchestrates chatbot analytics interactions."""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone, time as time_of_day
from typing import Any, Callable, Dict, List, Optional, Sequence, TypeVar

from ..infrastructure.database import DatabaseError, get_session
from ..models import FieldRecommendation
from ..repositories.analytics_repository import (
    ChatSessionRepository,
    ChatbotLogRepository,
    FeedbackRepository,
    IntentRepository,
    RecommendationRepository,
)

LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


class ChatbotAnalyticsService:

    def __init__(self, *, source_model: Optional[str] = None) -> None:
        self._source_model = source_model or os.getenv("RASA_SOURCE_MODEL")
        if not self._source_model:
            self._source_model = os.getenv("RASA_MODEL_NAME", "rasa-pro")
        self._max_attempts = 3
        self._base_retry_delay = 1.0

    def _execute_with_retries(self, operation: Callable[[], T], action: str) -> T:
        """Execute a database operation with retries and exponential backoff."""

        delay = self._base_retry_delay
        attempt = 1
        while True:
            try:
                return operation()
            except DatabaseError as exc:
                LOGGER.warning(
                    "[ChatbotAnalyticsService] %s failed on attempt %s/%s: %s",
                    action,
                    attempt,
                    self._max_attempts,
                    exc,
                )
                if attempt >= self._max_attempts:
                    LOGGER.error(
                        "[ChatbotAnalyticsService] giving up %s after %s attempts",
                        action,
                        attempt,
                    )
                    raise
                time.sleep(delay)
                attempt += 1
                delay = min(delay * 2, 5.0)

    # ------------------------------------------------------------------
    # Chat session helpers
    # ------------------------------------------------------------------
    def ensure_chat_session(
        self, user_id: int, theme: str, user_role: Optional[str]
    ) -> int:
        LOGGER.info(
            "[ChatbotAnalyticsService] ensure_chat_session user_id=%s theme=%s role=%s",
            user_id,
            theme,
            user_role,
        )
        def _operation() -> int:
            with get_session() as session:
                repository = ChatSessionRepository(session)
                session_id = repository.ensure_session(
                    user_id=user_id, theme=theme, user_role=user_role
                )
                LOGGER.info(
                    "[ChatbotAnalyticsService] chat session ready id=%s for user_id=%s",
                    session_id,
                    user_id,
                )
                return session_id

        return self._execute_with_retries(
            _operation, action="ensure_chat_session"
        )

    def close_chat_session(self, chatbot_id: int) -> None:
        LOGGER.info(
            "[ChatbotAnalyticsService] close_chat_session chatbot_id=%s",
            chatbot_id,
        )
        def _operation() -> None:
            with get_session() as session:
                repository = ChatSessionRepository(session)
                repository.close_session(chatbot_id)

        self._execute_with_retries(_operation, action="close_chat_session")

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

        LOGGER.info(
            "[ChatbotAnalyticsService] ensure_intent name=%s detected=%s false_positive=%s",
            intent_name,
            detected,
            false_positive,
        )

        def _fetch_existing() -> Optional[Dict[str, Any]]:
            with get_session() as session:
                repository = IntentRepository(session)
                return repository.fetch_by_name(intent_name)

        existing = self._execute_with_retries(
            _fetch_existing, action="fetch_intent"
        )

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

            def _update_operation() -> None:
                with get_session() as session:
                    repository = IntentRepository(session)
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

            self._execute_with_retries(
                _update_operation, action="update_intent"
            )
            LOGGER.debug(
                "[ChatbotAnalyticsService] updated intent id=%s total_detected=%s",
                existing["id_intent"],
                total_detected,
            )
            return int(existing["id_intent"])

        examples_text = "\n".join(sorted(cleaned_examples))

        def _create_operation() -> int:
            with get_session() as session:
                repository = IntentRepository(session)
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

        intent_id = self._execute_with_retries(
            _create_operation, action="create_intent"
        )
        LOGGER.debug(
            "[ChatbotAnalyticsService] created intent id=%s name=%s",
            intent_id,
            intent_name,
        )
        return intent_id

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
        LOGGER.info(
            "[ChatbotAnalyticsService] create_recommendation_log field_id=%s user_id=%s status=%s",
            field_id,
            user_id,
            status,
        )
        def _operation() -> int:
            with get_session() as session:
                repository = RecommendationRepository(session)
                return repository.create_log(
                    status=status,
                    message=message,
                    suggested_start=suggested_start,
                    suggested_end=suggested_end,
                    field_id=field_id,
                    user_id=user_id,
                )

        recommendation_id = self._execute_with_retries(
            _operation, action="create_recommendation_log"
        )
        LOGGER.info(
            "[ChatbotAnalyticsService] recommendation log created id=%s",
            recommendation_id,
        )
        return recommendation_id

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
        LOGGER.info(
            "[ChatbotAnalyticsService] log_chatbot_message session_id=%s response_type=%s sender=%s",
            session_id,
            response_type,
            sender_type,
        )
        def _operation() -> None:
            with get_session() as session:
                repository = ChatbotLogRepository(session)
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

        self._execute_with_retries(_operation, action="log_chatbot_message")

    def fetch_recommendation_history(self, session_id: int, limit: int) -> List[Dict[str, Any]]:
        LOGGER.debug(
            "[ChatbotAnalyticsService] fetch_recommendation_history session_id=%s limit=%s",
            session_id,
            limit,
        )
        def _operation() -> List[Dict[str, Any]]:
            with get_session() as session:
                repository = RecommendationRepository(session)
                return repository.fetch_history(session_id, limit)

        return self._execute_with_retries(
            _operation, action="fetch_recommendation_history"
        )

    def fetch_field_recommendations(
        self,
        *,
        sport: Optional[str],
        surface: Optional[str],
        location: Optional[str],
        limit: int,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        target_time: Optional[time_of_day] = None,
        prioritize_price: bool = False,
        prioritize_rating: bool = False,
    ) -> List[FieldRecommendation]:
        LOGGER.debug(
            "[ChatbotAnalyticsService] fetch_field_recommendations sport=%s surface=%s location=%s limit=%s min_price=%s max_price=%s target_time=%s price_first=%s rating_first=%s",
            sport,
            surface,
            location,
            limit,
            min_price,
            max_price,
            target_time,
            prioritize_price,
            prioritize_rating,
        )
        def _operation() -> List[FieldRecommendation]:
            with get_session() as session:
                repository = RecommendationRepository(session)
                return repository.fetch_field_recommendations(
                    sport=sport,
                    surface=surface,
                    location=location,
                    limit=limit,
                    min_price=min_price,
                    max_price=max_price,
                    target_time=target_time,
                    prioritize_price=prioritize_price,
                    prioritize_rating=prioritize_rating,
                )

        return self._execute_with_retries(
            _operation, action="fetch_field_recommendations"
        )

    def fetch_feedback_for_user(self, user_id: int, limit: int) -> List[Dict[str, Any]]:
        LOGGER.debug(
            "[ChatbotAnalyticsService] fetch_feedback_for_user user_id=%s limit=%s",
            user_id,
            limit,
        )
        def _operation() -> List[Dict[str, Any]]:
            with get_session() as session:
                repository = FeedbackRepository(session)
                return repository.fetch_recent(user_id, limit)

        return self._execute_with_retries(
            _operation, action="fetch_feedback_for_user"
        )


chatbot_service = ChatbotAnalyticsService()

__all__ = ["ChatbotAnalyticsService", "DatabaseError", "chatbot_service"]
