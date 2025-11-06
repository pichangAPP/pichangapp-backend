"""Custom tracker store with resilient Postgres connectivity."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

from rasa.core.tracker_store import SQLTrackerStore
from sqlalchemy.exc import InterfaceError, OperationalError

LOGGER = logging.getLogger(__name__)


class ResilientSQLTrackerStore(SQLTrackerStore):
    """SQL tracker store that retries on transient database disconnects."""

    def __init__(
        self,
        domain,
        event_broker=None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        engine_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        prepared_kwargs = dict(engine_kwargs or {})
        connect_args = dict(prepared_kwargs.get("connect_args") or {})
        connect_args.setdefault("keepalives", 1)
        connect_args.setdefault("keepalives_idle", 60)
        connect_args.setdefault("keepalives_interval", 30)
        connect_args.setdefault("keepalives_count", 5)
        prepared_kwargs["connect_args"] = connect_args
        prepared_kwargs.setdefault("pool_pre_ping", True)
        prepared_kwargs.setdefault("pool_recycle", 900)
        prepared_kwargs.setdefault("pool_timeout", 30)
        prepared_kwargs.setdefault("pool_size", 5)
        prepared_kwargs.setdefault("max_overflow", 5)

        self._max_retries = max(1, int(max_retries))
        self._retry_delay = max(0.1, float(retry_delay))

        super().__init__(
            domain,
            event_broker=event_broker,
            engine_kwargs=prepared_kwargs,
            **kwargs,
        )

    def _reset_pool(self) -> None:
        engine = getattr(self, "engine", None)
        if engine is not None:
            try:
                engine.dispose()
            except Exception:  # pragma: no cover - best effort cleanup
                LOGGER.debug("Failed disposing tracker store engine", exc_info=True)

    @contextmanager
    def session_scope(self) -> Generator[Any, None, None]:
        attempt = 1
        while True:
            try:
                with super().session_scope() as session:
                    yield session
                break
            except (OperationalError, InterfaceError) as exc:
                LOGGER.warning(
                    "Tracker store database error on attempt %s/%s: %s",
                    attempt,
                    self._max_retries,
                    exc,
                )
                if attempt >= self._max_retries:
                    LOGGER.exception(
                        "Tracker store failed after %s attempts", attempt
                    )
                    raise
                self._reset_pool()
                time.sleep(min(self._retry_delay * attempt, 5.0))
                attempt += 1


__all__ = ["ResilientSQLTrackerStore"]
