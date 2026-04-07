from __future__ import annotations

from typing import List

from rasa_sdk import Action, Tracker
from rasa_sdk.events import EventType, UserUtteranceReverted
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from ..services.chatbot.intent_logging import record_intent_and_log as _record_intent_and_log


class ActionDefaultFallback(Action):
    """Fallback action used by RulePolicy when action confidence is too low."""

    def name(self) -> str:
        return "action_default_fallback"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        del domain
        dispatcher.utter_message(response="utter_default_fallback")

        await _record_intent_and_log(
            tracker=tracker,
            session_id=tracker.get_slot("chatbot_session_id"),
            user_id=tracker.get_slot("user_id"),
            response_text="Fallback",
            response_type="fallback",
        )
        return [UserUtteranceReverted()]


__all__ = ["ActionDefaultFallback"]
