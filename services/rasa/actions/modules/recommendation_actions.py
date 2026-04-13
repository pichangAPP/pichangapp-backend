from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from rasa_sdk import Action, Tracker
from rasa_sdk.events import EventType, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from ..models import FieldRecommendation
from ..services.chatbot_service import DatabaseError, chatbot_service
from ..services.chatbot.intent_logging import record_intent_and_log as _record_intent_and_log
from ..domain.chatbot.async_utils import run_in_thread
from ..domain.chatbot.context import (
    coerce_metadata as _coerce_metadata,
    redact_metadata_for_logging as _redact_metadata_for_logging,
)
from ..domain.chatbot.budget import (
    detect_rating_focus as _detect_rating_focus,
    extract_budget_preferences as _extract_budget_preferences,
    format_budget_range as _format_budget_range,
)
from ..domain.chatbot.preferences import (
    apply_default_preferences as _apply_default_preferences,
    build_preference_summary as _build_preference_summary,
    clean_surface as _clean_surface,
    extract_entity_values as _extract_entity_values,
    guess_preferences_from_context as _guess_preferences_from_context,
    is_noise_answer as _is_noise_answer,
)
from ..domain.chatbot.recommendations import (
    describe_field_size as _describe_field_size,
    describe_relaxations as _describe_relaxations,
    field_size_label as _field_size_label,
    normalize_sport_preference as _normalize_sport_preference,
    normalize_surface_preference as _normalize_surface_preference,
    serialize_filter_payload as _serialize_filter_payload,
)
from ..services.chatbot.recommendation_flow import (
    fetch_recommendations_with_relaxation as _fetch_recommendations_with_relaxation,
    persist_recommendation_logs as _persist_recommendation_logs,
)
from ..domain.chatbot.time_utils import (
    coerce_datetime as _coerce_datetime,
    coerce_time_value as _coerce_time_value,
    extract_time_components as _extract_time_components,
    parse_datetime as _parse_datetime,
)

LOGGER = logging.getLogger(__name__)


class ActionSubmitFieldRecommendationForm(Action):
    """Handle the submission of the field recommendation form."""

    def name(self) -> str:
        return "action_submit_field_recommendation_form"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        LOGGER.debug(
            "[ActionSubmitFieldRecommendationForm] slots before processing: %s",
            tracker.current_slot_values(),
        )
        user_message = tracker.latest_message.get("text") or ""
        raw_metadata = tracker.latest_message.get("metadata")
        latest_metadata = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
        user_id_raw = tracker.get_slot("user_id")
        theme = tracker.get_slot("chat_theme") or "Reservas y alquileres"
        role_slot = (tracker.get_slot("user_role") or "player").lower()
        user_role = "admin" if role_slot == "admin" else "player"

        LOGGER.info(
            "[ActionSubmitFieldRecommendationForm] incoming message=%s user_slot=%s role=%s metadata=%s",
            user_message,
            user_id_raw,
            user_role,
            _redact_metadata_for_logging(latest_metadata),
        )

        if not user_id_raw:
            response_text = (
                "No pude identificar tu usuario desde las credenciales. "
                "Vuelve a iniciar sesión y retomamos la búsqueda de canchas."
            )
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=None,
                user_id=None,
                response_text=response_text,
                response_type="recommendation_error",
            )
            return []

        try:
            user_id = int(str(user_id_raw).strip())
        except ValueError:
            response_text = (
                "Parece que tu sesión no trae un usuario válido. "
                "Prueba iniciando sesión otra vez y te ayudo con la reserva."
            )
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=None,
                user_id=None,
                response_text=response_text,
                response_type="recommendation_error",
            )
            return []

        try:
            session_id = await run_in_thread(
                chatbot_service.ensure_chat_session,
                user_id,
                theme,
                user_role,
            )
            LOGGER.info(
                "[ActionSubmitFieldRecommendationForm] ensured chat session id=%s for user_id=%s",
                session_id,
                user_id,
            )
        except DatabaseError:
            LOGGER.exception(
                "[ActionSubmitFieldRecommendationForm] database error ensuring session for user_id=%s",
                user_id,
            )
            response_text = (
                "En este momento no puedo conectarme a la base de datos para revisar las canchas. "
                "Inténtalo de nuevo en unos minutos."
            )
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=None,
                user_id=user_id,
                response_text=response_text,
                response_type="recommendation_error",
            )
            return []

        preferences = {
            "preferred_sport": tracker.get_slot("preferred_sport"),
            "preferred_surface": tracker.get_slot("preferred_surface"),
            "preferred_location": tracker.get_slot("preferred_location"),
            "preferred_date": tracker.get_slot("preferred_date"),
            "preferred_start_time": tracker.get_slot("preferred_start_time"),
            "preferred_end_time": tracker.get_slot("preferred_end_time"),
            "preferred_budget": tracker.get_slot("preferred_budget"),
        }
        for slot_name, preferred_key in [
            ("location", "preferred_location"),
            ("sport", "preferred_sport"),
            ("surface", "preferred_surface"),
            ("date", "preferred_date"),
            ("time", "preferred_start_time"),
            ("budget", "preferred_budget"),
        ]:
            slot_value = tracker.get_slot(slot_name)
            if slot_value:
                preferences[preferred_key] = slot_value
        if not preferences["preferred_location"]:
            location_slot = tracker.get_slot("location")
            if isinstance(location_slot, str) and location_slot.strip():
                preferences["preferred_location"] = location_slot.strip()
        inferred_preferences = _guess_preferences_from_context(tracker)
        inference_events: List[EventType] = []
        inference_notes: List[str] = []
        inference_templates = {
            "preferred_location": "Asumí {value} como zona porque la mencionaste.",
            "preferred_date": "Tomé {value} como fecha solicitada.",
            "preferred_start_time": "Consideré {value} como horario estimado.",
            "preferred_surface": "Usé la superficie {value} que describiste.",
            "preferred_sport": "Entendí que buscas jugar {value}.",
        }
        for slot_name, template in inference_templates.items():
            if not preferences.get(slot_name) and inferred_preferences.get(slot_name):
                value = inferred_preferences[slot_name]
                preferences[slot_name] = value
                inference_events.append(SlotSet(slot_name, value))
                inference_notes.append(template.format(value=value))
        if not preferences.get("preferred_end_time") and inferred_preferences.get("preferred_end_time"):
            preferences["preferred_end_time"] = inferred_preferences["preferred_end_time"]
            inference_events.append(SlotSet("preferred_end_time", preferences["preferred_end_time"]))

        requested_location_value = tracker.get_slot("location") or preferences["preferred_location"]
        requested_surface_value = (
            tracker.get_slot("surface") or preferences["preferred_surface"]
        )
        requested_time_value = tracker.get_slot("time") or preferences["preferred_start_time"]
        user_requested_location = bool(requested_location_value)
        user_requested_time = bool(requested_time_value)

        preferences = _apply_default_preferences(preferences, latest_metadata)
        for slot_name in ("preferred_date", "preferred_start_time", "preferred_end_time"):
            if not tracker.get_slot(slot_name) and preferences.get(slot_name):
                inference_events.append(SlotSet(slot_name, preferences[slot_name]))

        preferred_sport = preferences["preferred_sport"]
        preferred_surface = preferences["preferred_surface"]
        preferred_location = preferences["preferred_location"]
        preferred_date = preferences["preferred_date"]
        preferred_start_time = preferences["preferred_start_time"]
        preferred_end_time = preferences["preferred_end_time"]
        min_budget, max_budget, price_focus = _extract_budget_preferences(tracker)
        target_time = _coerce_time_value(preferred_start_time)
        prioritize_price = price_focus or min_budget is not None or max_budget is not None
        rating_focus = _detect_rating_focus(user_message) or _detect_rating_focus(
            latest_metadata.get("query") if isinstance(latest_metadata.get("query"), str) else None
        )
        prioritize_rating = rating_focus
        sport_for_query = _normalize_sport_preference(preferred_sport)
        surface_for_query = _normalize_surface_preference(preferred_surface)

        requested_filters = _serialize_filter_payload(
            sport=sport_for_query,
            surface=surface_for_query,
            location=preferred_location,
            min_price=min_budget,
            max_price=max_budget,
            target_time=target_time,
            prioritize_price=prioritize_price,
            prioritize_rating=prioritize_rating,
        )

        try:
            (
                recommendations,
                applied_filters,
                relaxation_notes,
                search_strategy,
                relaxation_drops,
            ) = await _fetch_recommendations_with_relaxation(
                sport=sport_for_query,
                surface=surface_for_query,
                location=preferred_location,
                min_price=min_budget,
                max_price=max_budget,
                target_time=target_time,
                prioritize_price=prioritize_price,
                prioritize_rating=prioritize_rating,
                limit=3,
            )
        except DatabaseError:
            error_text = (
                "No pude consultar las canchas disponibles en este momento. "
                "Por favor, intenta de nuevo más tarde."
            )
            dispatcher.utter_message(text=error_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=user_id,
                response_text=error_text,
                response_type="recommendation_error",
            )
            return [SlotSet("chatbot_session_id", str(session_id))]

        if not recommendations:
            if preferred_sport:
                location_hint = f" en {preferred_location}" if preferred_location else ""
                not_found_text = (
                    f"No encontré canchas de {preferred_sport}{location_hint} con los filtros que me diste. "
                    "¿Quieres que pruebe con otra zona u horario?"
                )
                dispatcher.utter_message(text=not_found_text)
                await _record_intent_and_log(
                    tracker=tracker,
                    session_id=session_id,
                    user_id=user_id,
                    response_text=not_found_text,
                    response_type="recommendation_empty",
                )
                return inference_events + [SlotSet("chatbot_session_id", str(session_id))]

            try:
                general_recommendations: List[FieldRecommendation] = await run_in_thread(
                    chatbot_service.fetch_field_recommendations,
                    sport=None,
                    surface=None,
                    location=None,
                    limit=3,
                    min_price=None,
                    max_price=None,
                    target_time=None,
                    prioritize_price=prioritize_price,
                    prioritize_rating=prioritize_rating,
                )
            except DatabaseError:
                general_recommendations = []

            if general_recommendations:
                recommendations = general_recommendations
                applied_filters = _serialize_filter_payload(
                    sport=None,
                    surface=None,
                    location=None,
                    min_price=None,
                    max_price=None,
                    target_time=None,
                    prioritize_price=prioritize_price,
                    prioritize_rating=prioritize_rating,
                )
                relaxation_notes.append("Mostré sugerencias generales para que no te quedes sin opciones.")
                search_strategy = "global_backup"
            else:
                LOGGER.warning(
                    "[ActionSubmitFieldRecommendationForm] no recommendations found for session=%s user_id=%s",
                    session_id,
                    user_id,
                )
                not_found_text = (
                    "No encontré canchas disponibles ni ampliando la búsqueda. "
                    "¿Te gustaría que revise con otros horarios, zonas o deportes?"
                )
                dispatcher.utter_message(text=not_found_text)
                await _record_intent_and_log(
                    tracker=tracker,
                    session_id=session_id,
                    user_id=user_id,
                    response_text=not_found_text,
                    response_type="recommendation_empty",
                )
                return [SlotSet("chatbot_session_id", str(session_id))]

        budget_filtered = []
        if max_budget is not None:
            budget_filtered = [
                rec for rec in recommendations if rec.price_per_hour <= max_budget
            ]
            if budget_filtered:
                recommendations = budget_filtered
                relaxation_notes = [
                    note
                    for note in relaxation_notes
                    if not note.startswith("No había canchas exactas en ese presupuesto")
                ]

        top_choice = recommendations[0]
        start_dt = _parse_datetime(preferred_date, preferred_start_time)
        end_dt = start_dt + timedelta(hours=1)
        if preferred_end_time:
            try:
                end_dt = _parse_datetime(preferred_date, preferred_end_time)
            except ValueError:
                end_dt = start_dt + timedelta(hours=1)

        summary_lines: List[str] = []
        for idx, rec in enumerate(recommendations, start=1):
            price_text = f"S/ {rec.price_per_hour:.2f}"
            rating_text = ""
            if rec.rating is not None:
                rating_text = f" Calificación {rec.rating:.1f}/5."
            hours_text = ""
            open_short = rec.open_time[:5] if rec.open_time else ""
            close_short = rec.close_time[:5] if rec.close_time else ""
            if open_short and close_short:
                hours_text = f" Horario {open_short}-{close_short}."
            elif open_short:
                hours_text = f" Abre desde {open_short}."
            elif close_short:
                hours_text = f" Cierra alrededor de {close_short}."
            surface_label = rec.surface or "superficie mixta"
            if user_role == "admin":
                line = (
                    f"- {rec.field_name} · {rec.campus_name} ({rec.district}) · "
                    f"{rec.sport_name} / {surface_label} · capacidad {rec.capacity} · {price_text}/h."
                )
            else:
                line = (
                    f"- {rec.field_name} en {rec.campus_name} ({rec.district}). "
                    f"{rec.sport_name} en {surface_label}, espacio para {rec.capacity} y tarifa aproximada {price_text}."
                )
            size_info = _describe_field_size(rec.measurement)
            if size_info:
                line = f"{line} {size_info}."
            if rating_text or hours_text:
                line = f"{line}{rating_text}{hours_text}"
            summary_lines.append(line)

        if user_role == "admin":
            intro = "Estas son las alternativas que mejor se ajustan a su equipo:"
            closing = "Si requiere coordinar disponibilidad extra o apoyo con la gestión, avíseme."
        else:
            intro = "Aquí tienes opciones que se ajustan a lo que buscas para tu partido:"
            closing = "Si quieres que reserve alguna opción o busque algo distinto, solo dime."

        filter_fragments: List[str] = []
        location_used = applied_filters.get("location")
        location_relaxed = "location" in relaxation_drops
        found_location = location_used or top_choice.district
        if location_used:
            filter_fragments.append(f"en {location_used}")
        target_time_str = applied_filters.get("target_time")
        if target_time_str and user_requested_time:
            filter_fragments.append(f"para alrededor de las {target_time_str}")
        budget_phrase = _format_budget_range(
            applied_filters.get("min_price"),
            applied_filters.get("max_price"),
        )
        if budget_phrase:
            filter_fragments.append(budget_phrase)
        elif prioritize_price:
            filter_fragments.append("las opciones más económicas disponibles")
        if applied_filters.get("rating_priority"):
            filter_fragments.append("las mejor valoradas disponibles")
        filters_sentence = ""
        if filter_fragments:
            filters_sentence = " Consideré " + ", ".join(filter_fragments) + "."
        notes_sentence = ""
        if relaxation_notes:
            notes_sentence = " " + " ".join(relaxation_notes)
        inference_sentence = ""
        if inference_notes:
            inference_sentence = " " + " ".join(inference_notes)

        location_note: Optional[str] = None
        if (
            user_requested_location
            and requested_location_value
            and location_relaxed
            and found_location
            and requested_location_value.strip().lower()
            != location_used.strip().lower()
        ):
            surface_label = requested_surface_value or "esa superficie"
            location_note = (
                f"Perfecto, reviso opciones en {requested_location_value} con {surface_label}. "
                f"No encontré {surface_label} en {requested_location_value} pero sí en {found_location}."
            )
        context_intro = location_note or intro
        base_intro = f"{context_intro}{filters_sentence}{notes_sentence}{inference_sentence}"
        if user_role == "admin":
            response_text = (
                f"{base_intro}\n"
                + "\n".join(summary_lines)
                + f"\n{closing}"
            )
        else:
            response_text = base_intro
        recommendation_id, recommendation_ids = await _persist_recommendation_logs(
            user_id=user_id,
            recommendations=recommendations,
            summaries=summary_lines,
            start_dt=start_dt,
            end_dt=end_dt,
        )

        intent_data = tracker.latest_message.get("intent") or {}
        intent_name = intent_data.get("name") or "request_field_recommendation"
        confidence = intent_data.get("confidence")
        source_model = latest_metadata.get("model") or latest_metadata.get("pipeline")

        recommendation_payload = [
            {
                "id_field": rec.id_field,
                "field_name": rec.field_name,
                "campus_name": rec.campus_name,
                "district": rec.district,
                "address": rec.address,
                "surface": rec.surface,
                "capacity": rec.capacity,
                "price_per_hour": rec.price_per_hour,
                "open_time": rec.open_time,
                "close_time": rec.close_time,
                "rating": rec.rating,
                "measurement": rec.measurement,
                "size_category": _field_size_label(rec.measurement),
                "summary": summary,
            }
            for rec, summary in zip(recommendations, summary_lines)
        ]

        analytics_payload: Dict[str, Any] = {
            "response_type": "recommendation",
            "suggested_start": start_dt.isoformat(),
            "suggested_end": end_dt.isoformat(),
            "recommended_field_id": top_choice.id_field,
            "candidate_recommendations": recommendation_payload,
            "filters": {
                "requested": requested_filters,
                "applied": applied_filters,
            },
            "filter_summary": filter_fragments,
            "relaxation_notes": relaxation_notes,
            "inference_notes": inference_notes,
            "search_strategy": search_strategy,
            "recommendation_id": recommendation_id,
            "recommendation_ids": recommendation_ids,
            "intent_name": intent_name,
            "intent_confidence": confidence,
            "source_model": source_model,
            "user_message": user_message,
            "intent_examples": (
                [user_message]
                if user_message
                else ([intent_name] if intent_name else [])
            ),
            "response_template": response_text,
        }

        response_metadata = {
            "analytics": analytics_payload,
            "fields": recommendation_payload,
        }
        dispatcher.utter_message(
            text=response_text,
            metadata=response_metadata,
            json_message={"fields": recommendation_payload},
        )
        await _record_intent_and_log(
            tracker=tracker,
            session_id=session_id,
            user_id=user_id,
            response_text=response_text,
            response_type="recommendation",
            recommendation_id=recommendation_id,
            message_metadata=response_metadata,
        )

        events: List[EventType] = inference_events + [
            SlotSet("chatbot_session_id", str(session_id)),
            SlotSet("preferred_end_time", preferred_end_time or end_dt.isoformat()),
        ]
        return events


class ActionLogFieldRecommendationRequest(Action):
    """Log the initial user utterance before launching the recommendation form."""

    def name(self) -> str:
        return "action_log_field_recommendation_request"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        if tracker.active_loop_name == "field_recommendation_form":
            return []

        session_id = tracker.get_slot("chatbot_session_id")
        user_id = tracker.get_slot("user_id")

        reset_slots = [
            "preferred_sport",
            "preferred_surface",
            "preferred_location",
            "preferred_date",
            "preferred_start_time",
            "preferred_end_time",
            "preferred_budget",
        ]
        reset_events: List[EventType] = [SlotSet(slot_name, None) for slot_name in reset_slots]

        inferred_preferences = _guess_preferences_from_context(tracker)
        inferred_preferences = _apply_default_preferences(
            inferred_preferences,
            _coerce_metadata(tracker.latest_message.get("metadata")),
        )

        slot_events: List[EventType] = []
        for slot_name, value in inferred_preferences.items():
            if slot_name.startswith("preferred_") and value:
                slot_events.append(SlotSet(slot_name, value))
        entity_locations = _extract_entity_values(tracker, "location")
        resolved_location = tracker.get_slot("location")
        if not resolved_location and entity_locations:
            resolved_location = entity_locations[0]
        if resolved_location:
            inferred_preferences["preferred_location"] = resolved_location
            slot_events.append(SlotSet("preferred_location", resolved_location))
        surface_slot = tracker.get_slot("surface")
        if surface_slot:
            inferred_preferences["preferred_surface"] = surface_slot
            slot_events.append(SlotSet("preferred_surface", surface_slot))

        summary_text = _build_preference_summary(inferred_preferences)
        response_text = summary_text or "Perfecto, dime los detalles y voy filtrando opciones para ti."
        dispatcher.utter_message(text=response_text)

        await _record_intent_and_log(
            tracker=tracker,
            session_id=session_id,
            user_id=user_id,
            response_text=response_text,
            response_type="recommendation_request_log",
            message_metadata={"stage": "form_start", "preferences": inferred_preferences},
        )
        return reset_events + slot_events


class ActionShowRecommendationHistory(Action):
    """Return a summary of previous recommendations for the current session."""

    def name(self) -> str:
        return "action_show_recommendation_history"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        session_id = tracker.get_slot("chatbot_session_id")
        user_id_raw = tracker.get_slot("user_id")
        role_slot = (tracker.get_slot("user_role") or "player").lower()
        user_role = "admin" if role_slot == "admin" else "player"
        events: List[EventType] = []

        if not user_id_raw:
            response_text = (
                "No encuentro tu usuario activo. Inicia sesión nuevamente para revisar tu historial."
            )
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=None,
                response_text=response_text,
                response_type="history_error",
            )
            return []

        try:
            user_id = int(str(user_id_raw).strip())
        except ValueError:
            response_text = "Necesito que vuelvas a iniciar sesión para identificarte correctamente."
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=None,
                response_text=response_text,
                response_type="history_error",
            )
            return []

        if not session_id:
            try:
                new_session_id = await run_in_thread(
                    chatbot_service.ensure_chat_session,
                    user_id,
                    tracker.get_slot("chat_theme") or "Reservas y alquileres",
                    user_role,
                )
                session_id = str(new_session_id)
                events.append(SlotSet("chatbot_session_id", session_id))
            except DatabaseError:
                error_text = (
                    "No logré conectar con el historial en este momento. Intenta nuevamente en unos minutos."
                )
                dispatcher.utter_message(text=error_text)
                await _record_intent_and_log(
                    tracker=tracker,
                    session_id=None,
                    user_id=user_id,
                    response_text=error_text,
                    response_type="history_error",
                )
                return events

        try:
            history = await run_in_thread(
                chatbot_service.fetch_recommendation_history,
                int(session_id),
                3,
            )
        except DatabaseError:
            error_text = (
                "No pude revisar el historial de recomendaciones en este momento. Intenta luego, por favor."
            )
            dispatcher.utter_message(text=error_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=user_id,
                response_text=error_text,
                response_type="history_error",
            )
            return events

        if not history:
            empty_text = (
                "Todavía no he generado recomendaciones en esta conversación. Cuando tenga alguna, te las resumiré aquí."
            )
            dispatcher.utter_message(text=empty_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=user_id,
                response_text=empty_text,
                response_type="history_empty",
            )
            return events

        lines = []
        for record in history:
            suggested_dt = _coerce_datetime(record["suggested_time_start"])
            suggested_start = suggested_dt.strftime("%d/%m %H:%M")
            lines.append(
                (
                    f"- {record['field_name']} para {record['sport_name']} en {record['campus_name']} "
                    f"(estado: {record['status']}, sugerido para {suggested_start})."
                )
            )

        if user_role == "admin":
            header = "Aquí tiene el resumen de las recomendaciones más recientes:"
        else:
            header = "Te dejo un resumen de las canchas que te sugerí últimamente:"

        response_text = f"{header}\n" + "\n".join(lines)
        dispatcher.utter_message(text=response_text)
        await _record_intent_and_log(
            tracker=tracker,
            session_id=session_id,
            user_id=user_id,
            response_text=response_text,
            response_type="history",
            message_metadata={"history": history},
        )
        return events


__all__ = [
    "ActionSubmitFieldRecommendationForm",
    "ActionLogFieldRecommendationRequest",
    "ActionShowRecommendationHistory",
]
