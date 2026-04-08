"""Async-friendly tracker store that mirrors events into analytics."""

from __future__ import annotations

import asyncio
import logging
from contextlib import contextmanager
from typing import Any, Dict, Optional

from rasa.core.tracker_store import SQLTrackerStore
from rasa.shared.core.events import BotUttered, SessionStarted, UserUttered
from rasa.shared.core.trackers import DialogueStateTracker
from sqlalchemy.exc import InterfaceError, OperationalError

from actions.infrastructure.database import get_session
from actions.repositories.analytics.analytics_repository import IntentRepository
from actions.services.chatbot_service import DatabaseError, chatbot_service

LOGGER = logging.getLogger(__name__)
ASSUMED_INTENT_CONFIDENCE_THRESHOLD = 0.75


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
        self._last_intent_context: Dict[str, Dict[str, Any]] = {}

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
        # NOTE:
        # `contextmanager` generators cannot continue and yield again after an
        # exception is thrown from the caller's `with` block. Doing so causes:
        # "RuntimeError: generator didn't stop after throw()".
        #
        # Keep this scope simple and let Rasa's AuthRetryTrackerStore handle
        # retries at the call-site level.
        try:
            with super().session_scope() as session:
                yield session
        except (OperationalError, InterfaceError) as exc:
            LOGGER.warning("Tracker store database error: %s", exc)
            self._reset_pool()
            raise

    async def retrieve(self, sender_id: str) -> Optional[DialogueStateTracker]:
        try:
            return await super().retrieve(sender_id)
        except (OperationalError, InterfaceError, RuntimeError) as exc:
            LOGGER.warning(
                "Tracker store retrieve failed for sender '%s'. Using empty tracker. Error: %s",
                sender_id,
                exc,
            )
            self._reset_pool()
            self._last_event_index.pop(sender_id, None)
            self._pending_user_events.pop(sender_id, None)
            self._last_intent_context.pop(sender_id, None)
            return None

    async def save(self, tracker: DialogueStateTracker) -> None:
        try:
            await super().save(tracker)
        except (OperationalError, InterfaceError, RuntimeError) as exc:
            LOGGER.warning(
                "Tracker store save failed for sender '%s'. Continuing without persistence. Error: %s",
                tracker.sender_id,
                exc,
            )
            self._reset_pool()
            return

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
                self._last_intent_context.pop(sender_id, None)
                new_last_index = max(new_last_index, index)
                continue
            if isinstance(event, UserUttered):
                self._capture_user_event(sender_id, event, session_id, user_id)
            elif isinstance(event, BotUttered):
                self._append_bot_event(sender_id, event)
            new_last_index = max(new_last_index, index)

        pending = self._pending_user_events.get(sender_id)
        if pending and pending.get("bot_responses"):
            self._flush_pending_exchange(
                sender_id=sender_id,
                tracker=tracker,
                session_id=session_id,
                user_id=user_id,
            )

        if new_last_index > last_index:
            self._last_event_index[sender_id] = new_last_index

    def _capture_user_event(
        self, sender_id: str, event: UserUttered, session_id: int, user_id: int
    ) -> None:
        if sender_id in self._pending_user_events:
            self._flush_pending_exchange(
                sender_id,
                tracker=None,
                session_id=session_id,
                user_id=user_id,
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
            "bot_responses": [],
            "response_types": [],
            "bot_metadata": [],
        }
        self._pending_user_events[sender_id] = pending_payload
        self._last_intent_context[sender_id] = {
            "intent_name": pending_payload.get("intent_name"),
            "confidence": pending_payload.get("confidence"),
            "metadata": dict(metadata),
            "text": pending_payload.get("text") or "",
        }

    def _append_bot_event(self, sender_id: str, event: BotUttered) -> None:
        pending = self._pending_user_events.get(sender_id)
        if not pending:
            return
        text = (event.text or "").strip()
        if text:
            pending.setdefault("bot_responses", []).append(text)
        metadata = event.metadata if isinstance(event.metadata, dict) else {}
        pending.setdefault("bot_metadata", []).append(metadata)
        response_type = metadata.get("response_type") if metadata else None
        if isinstance(response_type, str) and response_type.strip():
            pending.setdefault("response_types", []).append(response_type.strip())

    def _ensure_intent_id(
        self,
        *,
        intent_name: Optional[str],
        message_text: str,
        bot_response: str,
        confidence: Optional[float],
        metadata: Dict[str, Any],
        count_detection: bool,
    ) -> Optional[int]:
        if not intent_name:
            return None

        if not count_detection:
            try:
                with get_session() as session:
                    repository = IntentRepository(session)
                    existing = repository.fetch_by_name(intent_name)
                    if existing and existing.get("id_intent") is not None:
                        return int(existing["id_intent"])
            except DatabaseError:
                LOGGER.exception(
                    "[TrackerStore] Failed to fetch intent '%s' while mirroring",
                    intent_name,
                )
            return None

        try:
            with get_session() as session:
                repository = IntentRepository(session)
                existing = repository.fetch_by_name(intent_name)
                if existing and existing.get("id_intent") is not None:
                    existing_id = int(existing["id_intent"])
                else:
                    existing_id = None
        except DatabaseError:
            LOGGER.exception(
                "[TrackerStore] Failed to fetch intent '%s' while mirroring",
                intent_name,
            )
            return None

        source_model = (
            metadata.get("model")
            or metadata.get("model_name")
            or metadata.get("pipeline")
            or metadata.get("source_model")
        )
        example_phrase = message_text.strip() if message_text and message_text.strip() else intent_name
        detected = intent_name != "nlu_fallback"
        assumed_intent = (
            detected
            and confidence is not None
            and float(confidence) < ASSUMED_INTENT_CONFIDENCE_THRESHOLD
        )
        false_positive = (not detected) or assumed_intent
        try:
            ensured_id = chatbot_service.ensure_intent(
                intent_name=intent_name,
                example_phrases=[example_phrase],
                response_template=bot_response or "",
                confidence=confidence,
                detected=detected,
                false_positive=false_positive,
                source_model=source_model,
            )
            return ensured_id or existing_id
        except DatabaseError:
            LOGGER.exception(
                "[TrackerStore] Failed to ensure intent '%s' while mirroring",
                intent_name,
            )
            return existing_id

    def _flush_pending_exchange(
        self,
        sender_id: str,
        tracker: Optional[DialogueStateTracker],
        session_id: Optional[int],
        user_id: Optional[int],
    ) -> None:
        pending_user = self._pending_user_events.pop(sender_id, None)

        if not pending_user:
            return

        message_text = pending_user.get("text") or ""
        intent_name = pending_user.get("intent_name")
        confidence = pending_user.get("confidence")
        metadata = dict(pending_user.get("metadata") or {})
        bot_responses = [item for item in (pending_user.get("bot_responses") or []) if item]
        response_types = [item for item in (pending_user.get("response_types") or []) if item]
        bot_metadata = [item for item in (pending_user.get("bot_metadata") or []) if isinstance(item, dict)]

        if intent_name is None and tracker is not None:
            latest_message = getattr(tracker, "latest_message", None) or {}
            intent_data = latest_message.get("intent") or {}
            intent_name = intent_data.get("name")
            confidence = confidence if confidence is not None else intent_data.get("confidence")
            latest_metadata = latest_message.get("metadata")
            if isinstance(latest_metadata, dict):
                metadata.update(latest_metadata)

        bot_response = "\n".join(bot_responses)
        sender_type = "bot" if bot_response else "user"

        non_generic_types = [item for item in response_types if item != "bot"]
        if non_generic_types:
            response_type = non_generic_types[0]
        elif sender_type == "bot":
            response_type = "bot"
        else:
            response_type = "user"

        count_detection = True
        intent_id = self._ensure_intent_id(
            intent_name=intent_name,
            message_text=message_text,
            bot_response=bot_response,
            confidence=confidence,
            metadata=metadata,
            count_detection=count_detection,
        )

        if bot_responses:
            metadata.setdefault("bot_messages_count", len(bot_responses))
            metadata.setdefault("bot_messages", bot_responses)
        if response_types:
            metadata.setdefault("response_types", response_types)
        if bot_metadata:
            metadata.setdefault("bot_metadata", bot_metadata)

        try:
            chatbot_service.log_chatbot_message(
                session_id=session_id or 0,
                intent_id=intent_id,
                recommendation_id=None,
                message_text=message_text,
                bot_response=bot_response,
                response_type=response_type,
                sender_type=sender_type,
                user_id=user_id,
                intent_confidence=confidence,
                metadata={**metadata, "intent_name": intent_name},
            )
        except DatabaseError:
            LOGGER.exception(
                "[TrackerStore] Failed to mirror exchange for sender_id=%s",
                sender_id,
            )
