from __future__ import annotations

import logging
from typing import List

from rasa_sdk import Action, Tracker
from rasa_sdk.events import EventType, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from ..services.chatbot.intent_logging import record_intent_and_log as _record_intent_and_log

LOGGER = logging.getLogger(__name__)

RECOMMENDATION_SLOTS = (
    "sport",
    "location",
    "time",
    "date",
    "budget",
    "surface",
    "rating",
    "num_players",
    "field_size",
    "urgency_level",
    "amenities",
    "form_abandoned",
    "last_action_context",
    "showed_pricing",
)


class ActionResetSlots(Action):
    def name(self) -> str:
        return "action_reset_slots"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        return [SlotSet(slot_name, None) for slot_name in RECOMMENDATION_SLOTS]


class ActionLogAbandonment(Action):
    def name(self) -> str:
        return "action_log_abandonment"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        await _record_intent_and_log(
            tracker=tracker,
            session_id=tracker.get_slot("chatbot_session_id"),
            user_id=tracker.get_slot("user_id"),
            response_text="Formulario de recomendación abandonado",
            response_type="form_abandoned",
        )
        return [SlotSet("form_abandoned", True)]


class ActionLogUrgentRequest(Action):
    def name(self) -> str:
        return "action_log_urgent_request"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        LOGGER.info("Urgent request detected for conversation=%s", tracker.sender_id)
        return [SlotSet("urgency_level", "urgente")]


class ActionCheckInactivity(Action):
    def name(self) -> str:
        return "action_check_inactivity"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        return []


class ActionLogConversationStart(Action):
    def name(self) -> str:
        return "action_log_conversation_start"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        await _record_intent_and_log(
            tracker=tracker,
            session_id=tracker.get_slot("chatbot_session_id"),
            user_id=tracker.get_slot("user_id"),
            response_text="Conversación iniciada",
            response_type="conversation_started",
        )
        return []


class ActionLogConversationEnd(Action):
    def name(self) -> str:
        return "action_log_conversation_end"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        await _record_intent_and_log(
            tracker=tracker,
            session_id=tracker.get_slot("chatbot_session_id"),
            user_id=tracker.get_slot("user_id"),
            response_text="Conversación finalizada",
            response_type="conversation_ended",
        )
        return []


class ActionValidateTime(Action):
    def name(self) -> str:
        return "action_validate_time"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        return []


class ActionValidateDate(Action):
    def name(self) -> str:
        return "action_validate_date"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        return []


class ActionValidateBudget(Action):
    def name(self) -> str:
        return "action_validate_budget"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        return []


class ActionLoadUserPreferences(Action):
    def name(self) -> str:
        return "action_load_user_preferences"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        return []


class ActionSaveUserPreferences(Action):
    def name(self) -> str:
        return "action_save_user_preferences"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        return []


class ActionCheckReturningUser(Action):
    def name(self) -> str:
        return "action_check_returning_user"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        return []


__all__ = [
    "ActionCheckInactivity",
    "ActionCheckReturningUser",
    "ActionLoadUserPreferences",
    "ActionLogAbandonment",
    "ActionLogConversationEnd",
    "ActionLogConversationStart",
    "ActionLogUrgentRequest",
    "ActionResetSlots",
    "ActionSaveUserPreferences",
    "ActionValidateBudget",
    "ActionValidateDate",
    "ActionValidateTime",
]
