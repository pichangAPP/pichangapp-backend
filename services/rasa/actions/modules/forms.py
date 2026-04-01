from __future__ import annotations

from typing import Any, Dict, List, Text

from rasa_sdk import FormValidationAction, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict


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
        normalized = slot_value.strip() if isinstance(slot_value, str) else slot_value
        return {
            "location": normalized,
            "preferred_location": normalized,
        }

    async def validate_time(
        self,
        slot_value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        normalized = slot_value.strip() if isinstance(slot_value, str) else slot_value
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
        return {"sport": slot_value}

    async def validate_time(
        self,
        slot_value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return {"time": slot_value}

    async def validate_date(
        self,
        slot_value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return {"date": slot_value}


__all__ = ["ValidateFieldRecommendationForm"]
