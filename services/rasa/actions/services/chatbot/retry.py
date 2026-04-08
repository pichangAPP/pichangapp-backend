from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

from ...infrastructure.database import DatabaseError

T = TypeVar("T")


class RetryExecutor:
    """Ejecuta operaciones con reintentos y backoff exponencial.

    Usado en: servicios de analytics del chatbot.
    """

    def __init__(
        self,
        *,
        max_attempts: int,
        base_delay: float,
        logger: logging.Logger,
    ) -> None:
        self._max_attempts = max_attempts
        self._base_delay = base_delay
        self._logger = logger

    def execute(self, operation: Callable[[], T], action: str) -> T:
        """Ejecuta una operacion con reintentos ante DatabaseError."""
        delay = self._base_delay
        attempt = 1
        while True:
            try:
                return operation()
            except DatabaseError as exc:
                self._logger.warning(
                    "[ChatbotAnalyticsService] %s failed on attempt %s/%s: %s",
                    action,
                    attempt,
                    self._max_attempts,
                    exc,
                )
                if attempt >= self._max_attempts:
                    self._logger.error(
                        "[ChatbotAnalyticsService] giving up %s after %s attempts",
                        action,
                        attempt,
                    )
                    raise
                time.sleep(delay)
                attempt += 1
                delay = min(delay * 2, 5.0)
