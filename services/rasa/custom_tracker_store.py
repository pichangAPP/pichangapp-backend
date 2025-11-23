"""Async-friendly tracker store that mirrors events into analytics."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Optional

from rasa.core.tracker_store import SQLTrackerStore
from rasa.shared.core.events import BotUttered, SessionStarted, UserUttered
from rasa.shared.core.trackers import DialogueStateTracker
from sqlalchemy.exc import InterfaceError, OperationalError

from actions.services.chatbot_service import DatabaseError, chatbot_service

LOGGER = logging.getLogger(__name__)


def _coerce_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            return int(stripped)
        return int(value)
    except (TypeError, ValueError):
        return None


class ResilientSQLTrackerStore(SQLTrackerStore):
    """Extends the default SQL tracker store with analytics mirroring."""

    def __init__(
        self,
        domain,
        event_broker=None,
        engine_kwargs: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
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
        prepared_kwargs.setdefault("pool_recycle", 600)
        prepared_kwargs.setdefault("pool_timeout", 30)
        prepared_kwargs.setdefault("pool_size", 5)
        prepared_kwargs.setdefault("max_overflow", 5)

        self._last_event_index: Dict[str, int] = {}
        self._pending_user_events: Dict[str, Dict[str, Any]] = {}
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
            except Exception:
                LOGGER.debug("Failed disposing tracker store engine", exc_info=True)

    @contextmanager
    def session_scope(self):
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

    async def save(self, tracker: DialogueStateTracker) -> None:
        await super().save(tracker)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            await loop.run_in_executor(
                None,
                self._mirror_events_into_analytics,
                tracker,
            )
        else:
            self._mirror_events_into_analytics(tracker)

    # ------------------------------------------------------------------
    # Analytics mirroring helpers
    # ------------------------------------------------------------------
    def _mirror_events_into_analytics(self, tracker: DialogueStateTracker) -> None:
        sender_id = tracker.sender_id
        if not sender_id:
            return

        session_id = _coerce_int(tracker.get_slot("chatbot_session_id"))
        user_id = _coerce_int(tracker.get_slot("user_id"))
        if session_id is None or user_id is None:
            return

        theme = tracker.get_slot("chat_theme") or "Reservas y alquileres"
        role = tracker.get_slot("user_role") or "player"

        try:
            chatbot_service.ensure_chat_session(user_id, theme, role)
        except DatabaseError:
            LOGGER.exception(
                "[TrackerStore] Unable to ensure chat session for user_id=%s", user_id
            )
            return

        last_index = self._last_event_index.get(sender_id, -1)
        new_last_index = last_index

        for index, event in enumerate(tracker.events):
            if index <= last_index:
                continue
            if isinstance(event, SessionStarted):
                self._pending_user_events.pop(sender_id, None)
                new_last_index = max(new_last_index, index)
                continue
            if isinstance(event, UserUttered):
                self._capture_user_event(sender_id, event, session_id, user_id)
            elif isinstance(event, BotUttered):
                self._persist_exchange(sender_id, tracker, event, session_id, user_id)
            new_last_index = max(new_last_index, index)

        if new_last_index > last_index:
            self._last_event_index[sender_id] = new_last_index

    def _capture_user_event(
        self, sender_id: str, event: UserUttered, session_id: int, user_id: int
    ) -> None:
        if sender_id in self._pending_user_events:
            pending = self._pending_user_events.pop(sender_id)
            self._persist_exchange(
                sender_id,
                tracker=None,
                bot_event=None,
                session_id=session_id,
                user_id=user_id,
                pending_user=pending,
            )

        intent_data = getattr(event, "intent", None) or {}
        parse_data = getattr(event, "parse_data", None) or {}
        metadata: Dict[str, Any] = {}
        if getattr(event, "metadata", None):
            metadata.update(event.metadata)
        if parse_data.get("metadata"):
            metadata.setdefault("nlu_metadata", parse_data.get("metadata"))

        pending_payload: Dict[str, Any] = {
            "text": getattr(event, "text", "") or "",
            "timestamp": getattr(event, "timestamp", None),
            "intent_name": intent_data.get("name"),
            "confidence": intent_data.get("confidence"),
            "metadata": metadata,
            "intent_ranking": parse_data.get("intent_ranking"),
            "source_model": metadata.get("model")
            or metadata.get("model_name")
            or parse_data.get("model"),
            "input_channel": getattr(event, "input_channel", None),
            "session_id": session_id,
            "user_id": user_id,
        }
        self._pending_user_events[sender_id] = pending_payload

    def _persist_exchange(
        self,
        sender_id: str,
        tracker: Optional[DialogueStateTracker],
        bot_event: Optional[BotUttered],
        session_id: Optional[int],
        user_id: Optional[int],
        pending_user: Optional[Dict[str, Any]] = None,
    ) -> None:
        if pending_user is None:
            pending_user = self._pending_user_events.pop(sender_id, None)
        else:
            cached = self._pending_user_events.get(sender_id)
            if cached is pending_user:
                self._pending_user_events.pop(sender_id, None)

        if not pending_user and not bot_event:
            return

        message_text = pending_user["text"] if pending_user else ""
        intent_name = pending_user.get("intent_name") if pending_user else None
        confidence = pending_user.get("confidence") if pending_user else None
        metadata = pending_user.get("metadata") if pending_user else {}

        bot_response = ""
        response_type = "user"
        if bot_event:
            bot_response = bot_event.text or ""
            response_type = bot_event.metadata.get("response_type", "bot") if bot_event.metadata else "bot"

        try:
            chatbot_service.log_chatbot_message(
                session_id=session_id or 0,
                intent_id=None,
                recommendation_id=None,
                message_text=message_text,
                bot_response=bot_response,
                response_type=response_type,
                sender_type="user" if bot_event is None else "bot",
                user_id=user_id,
                intent_confidence=confidence,
                metadata={**metadata, "intent_name": intent_name},
            )
        except DatabaseError:
            LOGGER.exception(
                "[TrackerStore] Failed to mirror exchange for sender_id=%s",
                sender_id,
            )
