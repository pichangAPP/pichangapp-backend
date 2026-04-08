from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ...infrastructure.database import get_session
from ...repositories.analytics.analytics_repository import ChatbotLogRepository
from .retry import RetryExecutor


class ChatbotLogOperations:
    """Operaciones para registrar mensajes del chatbot."""

    def __init__(self, *, executor: RetryExecutor, logger: logging.Logger) -> None:
        self._executor = executor
        self._logger = logger

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
        self._logger.info(
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

        self._executor.execute(_operation, action="log_chatbot_message")
