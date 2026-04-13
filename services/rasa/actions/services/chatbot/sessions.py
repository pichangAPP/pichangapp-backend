from __future__ import annotations

import logging
from typing import Optional

from ...infrastructure.database import get_session
from ...repositories.analytics.analytics_repository import ChatSessionRepository
from .retry import RetryExecutor


class ChatSessionOperations:
    """Operaciones de sesiones del chatbot (inicio/cierre)."""

    def __init__(
        self,
        *,
        executor: RetryExecutor,
        logger: logging.Logger,
    ) -> None:
        self._executor = executor
        self._logger = logger

    def ensure_chat_session(
        self, user_id: int, theme: str, user_role: Optional[str]
    ) -> int:
        self._logger.info(
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
                self._logger.info(
                    "[ChatbotAnalyticsService] chat session ready id=%s for user_id=%s",
                    session_id,
                    user_id,
                )
                return session_id

        return self._executor.execute(_operation, action="ensure_chat_session")

    def close_chat_session(self, chatbot_id: int) -> None:
        self._logger.info(
            "[ChatbotAnalyticsService] close_chat_session chatbot_id=%s",
            chatbot_id,
        )

        def _operation() -> None:
            with get_session() as session:
                repository = ChatSessionRepository(session)
                repository.close_session(chatbot_id)

        self._executor.execute(_operation, action="close_chat_session")
