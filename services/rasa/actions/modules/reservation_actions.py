from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from rasa_sdk import Action, Tracker
from rasa_sdk.events import EventType
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from ..services.chatbot.intent_logging import record_intent_and_log as _record_intent_and_log
from ..domain.chatbot.context import (
    coerce_metadata as _coerce_metadata,
    coerce_user_identifier as _coerce_user_identifier,
    extract_token_from_metadata as _extract_token_from_metadata,
)
from ..domain.chatbot.preferences import (
    extract_entity_values as _extract_entity_values,
)
from ..domain.chatbot.reservation import (
    describe_slot_availability as _describe_slot_availability,
    match_slot_status as _match_slot_status,
    rent_end_time as _rent_end_time,
    rent_start_time as _rent_start_time,
    select_target_rent as _select_target_rent,
)
from ..repositories.reservation.reservation_repository import (
    fetch_schedule_time_slots as _fetch_schedule_time_slots,
    fetch_user_rent_history as _fetch_user_rent_history,
)
from ..domain.chatbot.time_utils import (
    parse_date_value as _parse_date_value,
    parse_time_value as _parse_time_value,
)


class ActionReprogramReservation(Action):
    """Guide players through reprogramming their next reserved rent."""

    def name(self) -> str:
        return "action_reprogram_reservation"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        latest_message = tracker.latest_message or {}
        metadata = _coerce_metadata(latest_message.get("metadata"))
        session_id = tracker.get_slot("chatbot_session_id")
        user_token = _extract_token_from_metadata(metadata)

        user_id = None
        user_id_slot = tracker.get_slot("user_id")
        if user_id_slot:
            try:
                user_id = int(str(user_id_slot).strip())
            except ValueError:
                user_id = None
        if user_id is None:
            user_id = _coerce_user_identifier(metadata.get("user_id") or metadata.get("id_user"))

        if user_id is None:
            response_text = (
                "No logro identificar tu cuenta. Inicia sesión nuevamente para revisar la reserva."
            )
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=None,
                response_text=response_text,
                response_type="reprogram_error",
            )
            return []

        date_values = _extract_entity_values(tracker, "date")
        time_values = _extract_entity_values(tracker, "time")
        requested_date = _parse_date_value(date_values[0]) if date_values else None
        requested_time = _parse_time_value(time_values[0]) if time_values else None

        history = await _fetch_user_rent_history(
            user_id, token=user_token, status="reserved"
        )
        if not history:
            # Retry once in case the reservation service is still loading the history.
            await asyncio.sleep(0.35)
            history = await _fetch_user_rent_history(
                user_id, token=user_token, status="reserved"
            )
        if not history:
            response_text = (
                "No encuentro reservas activas en tu historial. "
                "Revisa la app y dime cuál quieres reprogramar."
            )
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=user_id,
                response_text=response_text,
                response_type="reprogram_error",
            )
            return []

        target_rent, selection_reason = _select_target_rent(
            history, requested_date, requested_time
        )
        if target_rent is None:
            response_text = (
                "No pude identificar una reserva en estado reservado. "
                "Indícame la fecha o el horario exacto para buscarla."
            )
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=user_id,
                response_text=response_text,
                response_type="reprogram_error",
            )
            return []

        start_dt = _rent_start_time(target_rent)
        end_dt = _rent_end_time(target_rent)
        schedule = target_rent.get("schedule") or {}
        if not schedule:
            schedules = target_rent.get("schedules") or []
            if schedules:
                schedule = schedules[0]
        field_info = schedule.get("field") or {}
        field_name = field_info.get("field_name") or "esa cancha"
        field_id = field_info.get("id_field")
        field_identifier: Optional[int] = None
        if field_id is not None:
            try:
                field_identifier = int(field_id)
            except (TypeError, ValueError):
                field_identifier = None

        availability_note = "No pude verificar la agenda de esa cancha."
        slot_status = None
        if field_identifier and start_dt:
            slots = await _fetch_schedule_time_slots(
                field_identifier, start_dt.date(), token=user_token
            )
            slot_status = _match_slot_status(slots, start_dt)
            availability_note = _describe_slot_availability(slot_status)

        date_label = (
            start_dt.strftime("%d/%m/%Y")
            if start_dt
            else requested_date.strftime("%d/%m/%Y")
            if requested_date
            else "la fecha indicada"
        )
        start_label = start_dt.strftime("%H:%M") if start_dt else target_rent.get("start_time") or ""
        end_label = end_dt.strftime("%H:%M") if end_dt else target_rent.get("end_time") or ""
        rent_id = target_rent.get("id_rent") or "tu renta"

        reason_note = selection_reason or ""
        response_parts = [
            (
                f"Tu renta #{rent_id} en {field_name} el {date_label} de "
                f"{start_label} a {end_label} puede reprogramarse, pero debes consultarle al administrador."
            ),
        ]
        if reason_note:
            response_parts.append(reason_note)
        response_parts.append(availability_note)
        response_text = " ".join(part for part in response_parts if part)

        response_metadata = {
            "rent_id": rent_id,
            "availability": slot_status,
        }
        dispatcher.utter_message(
            text=response_text,
            metadata=response_metadata,
            custom={"rent": target_rent},
        )
        await _record_intent_and_log(
            tracker=tracker,
            session_id=session_id,
            user_id=user_id,
            response_text=response_text,
            response_type="reprogram_request",
            message_metadata=response_metadata,
        )
        return []


__all__ = ["ActionReprogramReservation"]
