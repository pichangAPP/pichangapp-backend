from __future__ import annotations

import logging
from typing import List, Optional

from rasa_sdk import Action, Tracker
from rasa_sdk.events import EventType, SessionStarted, SlotSet
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
)

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
        metadata = _coerce_metadata(tracker.latest_message.get("metadata"))
        normalized_role = _normalize_role_from_metadata(metadata)
        if normalized_role is None:
            normalized_role = tracker.get_slot("user_role") or "player"
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
        metadata = _enrich_metadata_with_token(metadata)

        LOGGER.info(
            "[ActionSessionStart] conversation=%s metadata=%s slots=%s",
            tracker.sender_id,
            metadata,
            tracker.current_slot_values(),
        )

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

        if "token" in metadata and tracker.get_slot("user_token") != metadata["token"]:
            events.append(SlotSet("user_token", metadata["token"]))

        normalized_role = _normalize_role_from_metadata(metadata)
        if normalized_role:
            events.append(SlotSet("user_role", normalized_role))

        chat_theme = tracker.get_slot("chat_theme")
        if chat_theme:
            events.append(SlotSet("chat_theme", chat_theme))

        return events


__all__ = [
    "ActionEnsureUserRole",
    "ActionCloseChatSession",
    "ActionSessionStart",
]
