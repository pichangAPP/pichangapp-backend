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
    normalize_role_from_metadata as _normalize_role_from_metadata,
)

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
        metadata = _coerce_metadata(tracker.latest_message.get("metadata"))
        normalized_role = _normalize_role_from_metadata(metadata)
        events: List[EventType] = []
        if normalized_role and tracker.get_slot("user_role") != normalized_role:
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
