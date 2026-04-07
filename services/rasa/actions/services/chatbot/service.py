from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Sequence

from ...infrastructure.database import DatabaseError
from ...models import FieldRecommendation
from .feedback import FeedbackAnalyticsOperations
from .intents import IntentAnalyticsOperations
from .logs import ChatbotLogOperations
from .recommendations import RecommendationAnalyticsOperations
from .retry import RetryExecutor
from .sessions import ChatSessionOperations

LOGGER = logging.getLogger(__name__)


class ChatbotAnalyticsService:
    """Facade del servicio de analitica del chatbot."""

    def __init__(self, *, source_model: Optional[str] = None) -> None:
        self._source_model = source_model or os.getenv("RASA_SOURCE_MODEL")
        if not self._source_model:
            self._source_model = os.getenv("RASA_MODEL_NAME", "rasa-pro")
        self._max_attempts = 3
        self._base_retry_delay = 1.0

        executor = RetryExecutor(
            max_attempts=self._max_attempts,
            base_delay=self._base_retry_delay,
            logger=LOGGER,
        )
        self._sessions = ChatSessionOperations(executor=executor, logger=LOGGER)
        self._intents = IntentAnalyticsOperations(
            executor=executor,
            logger=LOGGER,
            source_model=self._source_model,
        )
        self._recommendations = RecommendationAnalyticsOperations(
            executor=executor, logger=LOGGER
        )
        self._logs = ChatbotLogOperations(executor=executor, logger=LOGGER)
        self._feedback = FeedbackAnalyticsOperations(executor=executor, logger=LOGGER)

    # ------------------------------------------------------------------
    # Chat session helpers
    # ------------------------------------------------------------------
    def ensure_chat_session(
        self, user_id: int, theme: str, user_role: Optional[str]
    ) -> int:
        return self._sessions.ensure_chat_session(user_id, theme, user_role)

    def close_chat_session(self, chatbot_id: int) -> None:
        self._sessions.close_chat_session(chatbot_id)

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
        return self._intents.ensure_intent(
            intent_name=intent_name,
            example_phrases=example_phrases,
            response_template=response_template,
            confidence=confidence,
            detected=detected,
            false_positive=false_positive,
            source_model=source_model,
        )

    def get_intent_id(self, intent_name: str) -> Optional[int]:
        return self._intents.get_intent_id(intent_name)

    # ------------------------------------------------------------------
    # Recommendation and log helpers
    # ------------------------------------------------------------------
    def create_recommendation_log(
        self,
        *,
        status: str,
        message: str,
        suggested_start: Any,
        suggested_end: Any,
        field_id: int,
        user_id: Optional[int],
    ) -> int:
        return self._recommendations.create_recommendation_log(
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
        self._logs.log_chatbot_message(
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
        return self._recommendations.fetch_recommendation_history(session_id, limit)

    def fetch_field_recommendations(
        self,
        *,
        sport: Optional[str],
        surface: Optional[str],
        location: Optional[str],
        limit: int,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        target_time: Optional[Any] = None,
        prioritize_price: bool = False,
        prioritize_rating: bool = False,
    ) -> List[FieldRecommendation]:
        return self._recommendations.fetch_field_recommendations(
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

    def fetch_feedback_for_user(self, user_id: int, limit: int) -> List[Dict[str, Any]]:
        return self._feedback.fetch_feedback_for_user(user_id, limit)


chatbot_service = ChatbotAnalyticsService()

__all__ = ["ChatbotAnalyticsService", "DatabaseError", "chatbot_service"]
