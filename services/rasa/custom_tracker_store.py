"""Custom tracker store with resilient Postgres connectivity and analytics mirroring."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Generator, Optional

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
    """SQL tracker store that retries transient errors and mirrors chats into analytics."""

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
        self._last_event_index: Dict[str, int] = {}
        self._pending_user_events: Dict[str, Dict[str, Any]] = {}

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

    def save(
        self, tracker: DialogueStateTracker, timeout: Optional[int] = None
    ) -> None:
        super().save(tracker, timeout=timeout)
        try:
            self._mirror_events_into_analytics(tracker)
        except Exception:  # pragma: no cover - defensive logging
            LOGGER.exception(
                "[TrackerStore] Failed to mirror events for sender_id=%s",
                tracker.sender_id,
            )

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

        # Ensure we have a session in analytics just in case the slot was hydrated
        # from a stale tracker without persisting the row.
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
            # Persist the previous message without a bot response to avoid data loss.
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
            # Ensure we remove the payload if it matches the in-memory cache
            cached = self._pending_user_events.get(sender_id)
            if cached is pending_user:
                self._pending_user_events.pop(sender_id, None)

        if session_id is None and pending_user:
            session_id = _coerce_int(pending_user.get("session_id"))
        if user_id is None and pending_user:
            user_id = _coerce_int(pending_user.get("user_id"))

        if session_id is None or user_id is None:
            # Try to derive the identifiers from cached payload when called
            # from the pending-user flush path.
            if tracker is not None:
                session_id = _coerce_int(tracker.get_slot("chatbot_session_id"))
                user_id = _coerce_int(tracker.get_slot("user_id"))
            if session_id is None or user_id is None:
                return

        latest_user_event: Optional[UserUttered] = None
        if tracker is not None:
            for tracked_event in reversed(tracker.events):
                if isinstance(tracked_event, UserUttered):
                    latest_user_event = tracked_event
                    break

        if bot_event is not None:
            metadata = dict(getattr(bot_event, "metadata", {}) or {})
        else:
            metadata = {}

        analytics_meta = metadata.get("analytics")
        skip_logging = False
        if isinstance(analytics_meta, dict):
            metadata_to_store = dict(analytics_meta)
            skip_logging = bool(analytics_meta.get("skip") or analytics_meta.get("logged_by_action"))
        else:
            metadata_to_store = {}
        if skip_logging:
            return

        message_text = ""
        intent_name: Optional[str] = None
        confidence: Optional[float] = None
        source_model: Optional[str] = None
        intent_examples = []
        intent_detected_name: Optional[str] = None

        if pending_user:
            message_text = pending_user.get("text") or ""
            intent_name = pending_user.get("intent_name")
            intent_detected_name = intent_name
            confidence = pending_user.get("confidence")
            source_model = pending_user.get("source_model")
            metadata_to_store.setdefault("user_event_metadata", pending_user.get("metadata"))
            if pending_user.get("intent_ranking"):
                metadata_to_store.setdefault(
                    "intent_ranking", pending_user.get("intent_ranking")
                )
            if pending_user.get("input_channel"):
                metadata_to_store.setdefault(
                    "input_channel", pending_user.get("input_channel")
                )
            intent_examples = [message_text] if message_text else []

        if latest_user_event is not None:
            if not message_text:
                message_text = getattr(latest_user_event, "text", "") or ""
            latest_intent = getattr(latest_user_event, "intent", None) or {}
            if not intent_name:
                intent_name = latest_intent.get("name")
                intent_detected_name = intent_name
            if confidence is None:
                confidence = latest_intent.get("confidence")
            latest_metadata = getattr(latest_user_event, "metadata", None) or {}
            if latest_metadata and "user_event_metadata" not in metadata_to_store:
                metadata_to_store["user_event_metadata"] = latest_metadata
            latest_parse = getattr(latest_user_event, "parse_data", None) or {}
            if (
                latest_parse.get("intent_ranking")
                and "intent_ranking" not in metadata_to_store
            ):
                metadata_to_store["intent_ranking"] = latest_parse.get(
                    "intent_ranking"
                )
            if latest_parse.get("metadata") and "nlu_metadata" not in metadata_to_store:
                metadata_to_store["nlu_metadata"] = latest_parse.get("metadata")
            if (
                latest_user_event.input_channel
                and "input_channel" not in metadata_to_store
            ):
                metadata_to_store["input_channel"] = latest_user_event.input_channel
            if not source_model:
                source_model = (
                    latest_metadata.get("model")
                    or latest_metadata.get("model_name")
                    or latest_parse.get("model")
                )
            if message_text and message_text not in intent_examples:
                intent_examples.append(message_text)

        response_text = ""
        response_template_text: Optional[str] = None
        response_type = "user_message"
        recommendation_id: Optional[int] = None

        if bot_event is not None:
            response_text = getattr(bot_event, "text", "") or ""
            metadata_to_store.setdefault("bot_event_metadata", metadata)
            analytics_section = metadata.get("analytics")
            if isinstance(analytics_section, dict):
                recommendation_id = analytics_section.get("recommendation_id")
                response_type = (
                    analytics_section.get("response_type") or "bot_response"
                )
                if analytics_section.get("intent_name") and not intent_name:
                    intent_name = analytics_section.get("intent_name")
                    intent_detected_name = intent_name
                if analytics_section.get("intent_confidence") and confidence is None:
                    confidence = analytics_section.get("intent_confidence")
                if analytics_section.get("source_model") and not source_model:
                    source_model = analytics_section.get("source_model")
                if analytics_section.get("user_message") and not message_text:
                    message_text = analytics_section.get("user_message")
                if analytics_section.get("intent_examples"):
                    intent_examples.extend(analytics_section.get("intent_examples"))
                response_template_text = analytics_section.get("response_template")
            else:
                response_type = metadata.get("utter_action") or "bot_response"
                response_template_text = response_text or response_type
        else:
            response_template_text = message_text or intent_name

        metadata_to_store.setdefault("tracker_sender_id", sender_id)
        event_timestamp_value: Optional[float] = None
        if bot_event is not None:
            raw_timestamp = getattr(bot_event, "timestamp", None)
            if raw_timestamp is not None:
                event_timestamp_value = float(raw_timestamp)
        if event_timestamp_value is None and pending_user:
            pending_ts = pending_user.get("timestamp")
            if pending_ts is not None:
                event_timestamp_value = float(pending_ts)
        if event_timestamp_value is None:
            event_timestamp_value = float(time.time())

        metadata_to_store.setdefault(
            "event_timestamp",
            datetime.utcfromtimestamp(event_timestamp_value).isoformat(),
        )
        if pending_user and pending_user.get("timestamp") is not None:
            metadata_to_store.setdefault(
                "user_event_timestamp",
                datetime.utcfromtimestamp(pending_user["timestamp"]).isoformat(),
            )

        metadata_to_store = {
            key: value
            for key, value in metadata_to_store.items()
            if value is not None
        }

        if not intent_examples and intent_name:
            intent_examples = [intent_name]

        intent_id: Optional[int] = None
        if intent_name:
            try:
                intent_id = chatbot_service.ensure_intent(
                    intent_name=intent_name,
                    example_phrases=[phrase for phrase in intent_examples if phrase],
                    response_template=
                    response_template_text
                    if response_template_text
                    else response_text
                    or intent_name,
                    confidence=confidence,
                    detected=bool(response_text or message_text),
                    false_positive=False,
                    source_model=source_model,
                )
            except DatabaseError:
                LOGGER.exception(
                    "[TrackerStore] Failed ensuring intent=%s for sender_id=%s",
                    intent_name,
                    sender_id,
                )

        if intent_detected_name and not metadata_to_store.get("intent_name"):
            metadata_to_store["intent_name"] = intent_detected_name
        if confidence is not None and "intent_confidence" not in metadata_to_store:
            metadata_to_store["intent_confidence"] = confidence
        if intent_id is not None and "intent_id" not in metadata_to_store:
            metadata_to_store["intent_id"] = intent_id

        try:
            chatbot_service.log_chatbot_message(
                session_id=session_id,
                intent_id=intent_id,
                recommendation_id=recommendation_id,
                message_text=message_text,
                bot_response=response_text,
                response_type=response_type,
                sender_type="user" if pending_user else "bot",
                user_id=user_id,
                intent_confidence=confidence,
                metadata=metadata_to_store,
            )
        except DatabaseError:
            LOGGER.exception(
                "[TrackerStore] Failed logging exchange for sender_id=%s session_id=%s",
                sender_id,
                session_id,
            )


__all__ = ["ResilientSQLTrackerStore"]
