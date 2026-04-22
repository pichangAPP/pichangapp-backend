"""Orchestration for intent persistence and chatbot logs."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from rasa_sdk import Tracker

from ...services.chatbot_service import DatabaseError, chatbot_service
from ...domain.chatbot.async_utils import run_in_thread
from ...domain.chatbot.context import coerce_metadata, coerce_user_identifier

LOGGER = logging.getLogger(__name__)
ACTION_SIDE_LOGGING_ENABLED = os.getenv("ACTION_SIDE_LOGGING_ENABLED", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


async def record_intent_and_log(
    *,
    tracker: Tracker,
    session_id: Optional[int | str],
    user_id: Optional[int | str],
    response_text: str,
    response_type: str,
    recommendation_id: Optional[int] = None,
    message_metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Persist chatbot log entry and attach intent id when available."""

    # Tracker-store mirroring is the primary source of truth to avoid duplicate
    # rows (one per BotUttered). Keep this opt-in for troubleshooting.
    if not ACTION_SIDE_LOGGING_ENABLED:
        return

    latest_message = tracker.latest_message or {}
    user_message = latest_message.get("text") or ""
    base_metadata = coerce_metadata(latest_message.get("metadata"))
    metadata: Dict[str, Any] = dict(base_metadata)
    if message_metadata:
        metadata.update(message_metadata)

    intent_data = latest_message.get("intent") or {}
    intent_name = intent_data.get("name") or "nlu_fallback"
    confidence = intent_data.get("confidence")
    intent_id: Optional[int] = None
    try:
        intent_id = await run_in_thread(
            chatbot_service.ensure_intent,
            intent_name,
            [user_message or intent_name],
            response_text,
            confidence=confidence,
            detected=(intent_name != "nlu_fallback"),
            false_positive=(intent_name == "nlu_fallback"),
        )
    except DatabaseError:
        LOGGER.exception(
            "[Analytics] Unable to ensure intent=%s for conversation=%s",
            intent_name,
            tracker.sender_id,
        )

    session_value = coerce_user_identifier(session_id) if session_id is not None else None
    user_value = coerce_user_identifier(user_id) if user_id is not None else None

    slot_session = tracker.get_slot("chatbot_session_id")
    if session_value is None and slot_session:
        session_value = coerce_user_identifier(slot_session)

    slot_user = tracker.get_slot("user_id")
    if user_value is None and slot_user:
        user_value = coerce_user_identifier(slot_user)

    if user_value is None:
        metadata_user = metadata.get("user_id") or metadata.get("id_user")
        user_value = coerce_user_identifier(metadata_user)

    if session_value is None:
        metadata_session = metadata.get("chatbot_session_id")
        session_value = coerce_user_identifier(metadata_session)

    if session_value is None and user_value is not None:
        theme = tracker.get_slot("chat_theme") or metadata.get("chat_theme") or "Reservas y alquileres"
        role_source = tracker.get_slot("user_role") or metadata.get("user_role") or metadata.get("role")
        role_name = "admin" if isinstance(role_source, str) and role_source.lower() == "admin" else "player"
        try:
            session_value = await run_in_thread(
                chatbot_service.ensure_chat_session,
                int(user_value),
                theme,
                role_name,
            )
            LOGGER.info(
                "[Analytics] ensured session_id=%s on the fly for sender=%s",
                session_value,
                tracker.sender_id,
            )
        except DatabaseError:
            LOGGER.exception(
                "[Analytics] unable to ensure session for user_id=%s while logging",
                user_value,
            )

    if session_value is None:
        LOGGER.debug(
            "[Analytics] Skipping chatbot log because session_id is missing for sender=%s",
            tracker.sender_id,
        )
        return

    metadata.setdefault("slots_snapshot", tracker.current_slot_values())
    if user_value is not None:
        metadata.setdefault("user_id", int(user_value))
        metadata.setdefault("id_user", int(user_value))
    metadata.setdefault("chatbot_session_id", session_value)

    try:
        await run_in_thread(
            chatbot_service.log_chatbot_message,
            session_id=session_value,
            intent_id=intent_id,
            recommendation_id=recommendation_id,
            message_text=user_message,
            bot_response=response_text,
            response_type=response_type,
            sender_type="bot",
            user_id=user_value,
            intent_confidence=confidence,
            metadata=metadata,
        )
    except DatabaseError:
        LOGGER.exception(
            "[Analytics] Failed to log chatbot message for session_id=%s",
            session_value,
        )
