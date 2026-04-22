from __future__ import annotations

from typing import Any, Dict, List, Text

from rasa_sdk import FormValidationAction, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from ..domain.chatbot.locale_canonical import resolve_lima_district, resolve_sport_canonical
from ..domain.chatbot.time_utils import coerce_time_value


class ValidateFieldRecommendationForm(FormValidationAction):
    """Validate the slots collected by the field recommendation form."""

    def name(self) -> str:
        return "validate_field_recommendation_form"

    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        base_slots: List[Text] = ["location", "sport", "time", "date"]
        if tracker.active_loop_name != "field_recommendation_form":
            return base_slots

        provided = [
            slot
            for slot in base_slots
            if tracker.get_slot(slot) not in (None, "", [], {})
        ]
        return base_slots if not provided else []

    async def validate_location(
        self,
        slot_value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        if not isinstance(slot_value, str) or not slot_value.strip():
            return {}
        resolved = resolve_lima_district(slot_value)
        if not resolved:
            return {}
        return {
            "location": resolved,
            "preferred_location": resolved,
        }

    async def validate_time(
        self,
        slot_value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        if not isinstance(slot_value, str) or not slot_value.strip():
            return {}
        raw = slot_value.strip()
        coerced = coerce_time_value(raw)
        if coerced is not None:
            normalized = coerced.strftime("%H:%M")
        else:
            normalized = raw
        return {
            "time": normalized,
            "preferred_start_time": normalized,
        }

    async def validate_sport(
        self,
        slot_value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        if not isinstance(slot_value, str) or not slot_value.strip():
            return {}
        resolved = resolve_sport_canonical(slot_value)
        if not resolved:
            return {}
        return {"sport": resolved}

    async def validate_date(
        self,
        slot_value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        if not isinstance(slot_value, str) or not slot_value.strip():
            return {}
        return {"date": slot_value.strip()}


__all__ = ["ValidateFieldRecommendationForm"]
