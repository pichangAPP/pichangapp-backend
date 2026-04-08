from __future__ import annotations

import logging
from typing import Any, Dict, List

from ...infrastructure.database import get_session
from ...repositories.analytics.analytics_repository import FeedbackRepository
from .retry import RetryExecutor


class FeedbackAnalyticsOperations:
    """Operaciones relacionadas al feedback de usuarios."""

    def __init__(self, *, executor: RetryExecutor, logger: logging.Logger) -> None:
        self._executor = executor
        self._logger = logger

    def fetch_feedback_for_user(self, user_id: int, limit: int) -> List[Dict[str, Any]]:
        self._logger.debug(
            "[ChatbotAnalyticsService] fetch_feedback_for_user user_id=%s limit=%s",
            user_id,
            limit,
        )

        def _operation() -> List[Dict[str, Any]]:
            with get_session() as session:
                repository = FeedbackRepository(session)
                return repository.fetch_recent(user_id, limit)

        return self._executor.execute(_operation, action="fetch_feedback_for_user")
