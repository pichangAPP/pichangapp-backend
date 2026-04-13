from __future__ import annotations

import logging
from typing import Any, List, Optional

from rasa_sdk import Action, Tracker
from rasa_sdk.events import ActionExecuted, EventType, SessionStarted, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from ..services.chatbot_service import DatabaseError, chatbot_service
from ..services.chatbot.intent_logging import record_intent_and_log as _record_intent_and_log
from ..domain.chatbot.async_utils import run_in_thread
from ..domain.chatbot.context import (
    coerce_metadata as _coerce_metadata,
    coerce_user_identifier as _coerce_user_identifier,
    enrich_metadata_with_token as _enrich_metadata_with_token,
    normalize_role_from_metadata as _normalize_role_from_metadata,
    redact_metadata_for_logging as _redact_metadata_for_logging,
    redact_slot_values_for_logging as _redact_slot_values_for_logging,
)
from ..infrastructure.config import get_settings
from ..infrastructure.security import extract_role_from_claims

LOGGER = logging.getLogger(__name__)


class ActionEnsureUserRole(Action):
    def name(self) -> str:
        return "action_ensure_user_role"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        metadata = _enrich_metadata_with_token(
            dict(_coerce_metadata(tracker.latest_message.get("metadata")))
        )
        enforce = get_settings().ENFORCE_JWT_FOR_ADMIN_ACTIONS
        claims = metadata.get("token_claims")
        if isinstance(claims, dict):
            normalized_role = extract_role_from_claims(claims) or "player"
        elif enforce:
            meta_role = _normalize_role_from_metadata(metadata)
            if meta_role == "admin":
                normalized_role = "player"
            else:
                normalized_role = meta_role or tracker.get_slot("user_role") or "player"
        else:
            normalized_role = _normalize_role_from_metadata(metadata)
            if normalized_role is None:
                normalized_role = tracker.get_slot("user_role") or "player"
        if normalized_role not in ("admin", "player"):
            normalized_role = "player"
        events: List[EventType] = []
        if tracker.get_slot("user_role") != normalized_role:
            events.append(SlotSet("user_role", normalized_role))
        return events


class ActionCloseChatSession(Action):
    """Mark the chatbot session as finished in the analytics database."""

    def name(self) -> str:
        return "action_close_chat_session"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        session_id = tracker.get_slot("chatbot_session_id")
        user_id = tracker.get_slot("user_id")
        response_text = "Sesión cerrada"
        if session_id:
            try:
                await run_in_thread(chatbot_service.close_chat_session, int(session_id))
            except (ValueError, DatabaseError):
                LOGGER.debug("Could not close session %s", session_id)
        await _record_intent_and_log(
            tracker=tracker,
            session_id=session_id,
            user_id=user_id,
            response_text=response_text,
            response_type="session_closed",
        )
        return []


class ActionSessionStart(Action):
    """Populate session slots from metadata at the beginning of a conversation."""

    def name(self) -> str:
        return "action_session_start"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        events: List[EventType] = [SessionStarted()]
        metadata = _coerce_metadata(tracker.latest_message.get("metadata"))
        if not metadata:
            metadata = _coerce_metadata(tracker.get_slot("session_started_metadata"))
        metadata = _enrich_metadata_with_token(dict(metadata))
        enforce = get_settings().ENFORCE_JWT_FOR_ADMIN_ACTIONS

        LOGGER.info(
            "[ActionSessionStart] conversation=%s metadata=%s slots=%s",
            tracker.sender_id,
            _redact_metadata_for_logging(metadata),
            _redact_slot_values_for_logging(tracker.current_slot_values()),
        )

        claims = metadata.get("token_claims")
        user_identifier: Any = None
        if isinstance(claims, dict):
            user_identifier = claims.get("id_user") or claims.get("sub")
        elif not enforce:
            user_identifier = metadata.get("user_id") or metadata.get("id_user")
            if user_identifier is None:
                nested_user = metadata.get("user")
                if isinstance(nested_user, dict):
                    user_identifier = nested_user.get("id") or nested_user.get("id_user")

        user_id: Optional[int] = None
        if user_identifier is not None:
            user_id = _coerce_user_identifier(user_identifier)
            if user_id is None:
                events.append(SlotSet("user_id", str(user_identifier)))
                LOGGER.warning(
                    "[ActionSessionStart] invalid user identifier=%s for conversation=%s",
                    user_identifier,
                    tracker.sender_id,
                )
            else:
                events.append(SlotSet("user_id", str(user_id)))
                LOGGER.info(
                    "[ActionSessionStart] user slot planned with id=%s for conversation=%s",
                    user_id,
                    tracker.sender_id,
                )

        normalized_role: Optional[str] = None
        if isinstance(claims, dict):
            normalized_role = extract_role_from_claims(claims)
        elif enforce:
            meta_role = _normalize_role_from_metadata(metadata)
            if meta_role == "admin":
                normalized_role = "player"
            else:
                normalized_role = meta_role
        else:
            normalized_role = _normalize_role_from_metadata(metadata)
        effective_role = normalized_role or tracker.get_slot("user_role") or "player"
        if effective_role not in ("admin", "player"):
            effective_role = "player"
        if tracker.get_slot("user_role") != effective_role:
            events.append(SlotSet("user_role", effective_role))

        chat_theme = tracker.get_slot("chat_theme") or "Reservas y alquileres"
        if tracker.get_slot("chat_theme") != chat_theme:
            events.append(SlotSet("chat_theme", chat_theme))

        if user_id is not None and not tracker.get_slot("chatbot_session_id"):
            try:
                ensured = await run_in_thread(
                    chatbot_service.ensure_chat_session,
                    user_id,
                    chat_theme,
                    effective_role,
                )
            except DatabaseError:
                LOGGER.exception(
                    "[ActionSessionStart] database error ensuring chat session for user_id=%s",
                    user_id,
                )
            else:
                events.append(SlotSet("chatbot_session_id", str(ensured)))

        if metadata:
            events.append(SlotSet("session_started_metadata", metadata))

        events.append(ActionExecuted("action_listen"))
        return events


__all__ = [
    "ActionEnsureUserRole",
    "ActionCloseChatSession",
    "ActionSessionStart",
]
