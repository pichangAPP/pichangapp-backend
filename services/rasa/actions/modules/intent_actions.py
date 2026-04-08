from __future__ import annotations

import logging
from typing import List

from rasa_sdk import Action, Tracker
from rasa_sdk.events import EventType, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from ..services.chatbot.intent_logging import record_intent_and_log as _record_intent_and_log
from ..domain.chatbot.context import (
    coerce_metadata as _coerce_metadata,
    enrich_metadata_with_token as _enrich_metadata_with_token,
    normalize_role_from_metadata as _normalize_role_from_metadata,
)
from ..infrastructure.config import get_settings
from ..infrastructure.security import extract_role_from_claims

LOGGER = logging.getLogger(__name__)


class ActionLogUserIntent(Action):
    """Ensure every handled intent is persisted in analytics."""

    def name(self) -> str:
        return "action_log_user_intent"

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

        await _record_intent_and_log(
            tracker=tracker,
            session_id=tracker.get_slot("chatbot_session_id"),
            user_id=tracker.get_slot("user_id"),
            response_text="",
            response_type="intent_log",
        )
        return events


__all__ = ["ActionLogUserIntent"]
