from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from rasa_sdk import Action, Tracker
from rasa_sdk.events import EventType, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from ..services.chatbot_service import DatabaseError, chatbot_service
from ..services.chatbot.intent_logging import record_intent_and_log as _record_intent_and_log
from ..domain.chatbot.async_utils import run_in_thread
from ..domain.chatbot.budget import (
    extract_budget_preferences as _extract_budget_preferences,
)
from ..domain.chatbot.context import (
    coerce_metadata as _coerce_metadata,
    coerce_user_identifier as _coerce_user_identifier,
    extract_token_from_metadata as _extract_token_from_metadata,
)
from ..domain.chatbot.preferences import (
    extract_entity_values as _extract_entity_values,
)
from ..domain.chatbot.time_utils import (
    coerce_time_value as _coerce_time_value,
)
from ..repositories.admin.admin_repository import (
    fetch_field_usage_from_analytics as _fetch_field_usage_from_analytics,
    fetch_managed_campuses as _fetch_managed_campuses,
    fetch_top_clients_from_analytics as _fetch_top_clients_from_analytics,
)

LOGGER = logging.getLogger(__name__)


class ActionProvideAdminManagementTips(Action):
    """Provide operational recommendations for admin users managing fields."""

    def name(self) -> str:
        return "action_provide_admin_management_tips"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        events: List[EventType] = []
        latest_message = tracker.latest_message or {}
        theme = tracker.get_slot("chat_theme") or "Reservas y alquileres"
        user_role = (tracker.get_slot("user_role") or "player").lower()
        user_id_raw = tracker.get_slot("user_id")
        session_id = tracker.get_slot("chatbot_session_id")
        metadata = _coerce_metadata(latest_message.get("metadata"))

        user_id: Optional[int] = None
        if user_id_raw:
            try:
                user_id = int(str(user_id_raw).strip())
            except ValueError:
                user_id = None
        if user_id is None:
            user_id = _coerce_user_identifier(metadata.get("user_id") or metadata.get("id_user"))

        if user_role != "admin":
            response_text = (
                "Estas recomendaciones operativas están disponibles para administradores. "
                "Inicia sesión con un perfil de gestión o indícame si buscas canchas para jugar."
            )
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=user_id,
                response_text=response_text,
                response_type="admin_recommendation_denied",
            )
            return events

        if user_id is None:
            response_text = (
                "No pude validar tu usuario administrador. Vuelve a iniciar sesión para revisar tus sedes."
            )
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=None,
                response_text=response_text,
                response_type="admin_recommendation_error",
            )
            return events

        if not session_id:
            try:
                ensured = await run_in_thread(
                    chatbot_service.ensure_chat_session,
                    user_id,
                    theme,
                    "admin",
                )
            except DatabaseError:
                LOGGER.exception(
                    "[ActionProvideAdminManagementTips] database error ensuring session for admin user_id=%s",
                    user_id,
                )
            else:
                session_id = str(ensured)
                events.append(SlotSet("chatbot_session_id", session_id))

        preferred_location = tracker.get_slot("preferred_location")
        entity_locations = _extract_entity_values(tracker, "location")
        location_focus = preferred_location or (entity_locations[0] if entity_locations else None)
        preferred_sport = tracker.get_slot("preferred_sport")
        sport_entities = _extract_entity_values(tracker, "sport")
        sport_focus = preferred_sport or (sport_entities[0] if sport_entities else None)
        start_time = tracker.get_slot("preferred_start_time")
        target_time = _coerce_time_value(start_time)
        min_budget, max_budget, price_focus = _extract_budget_preferences(tracker)

        tips: List[str] = []
        tips.append(
            "Revisa el dashboard de analytics para detectar conversaciones sin recomendación y activa seguimientos automáticos."
        )
        if location_focus:
            tips.append(
                f"Activa campañas hiperlocales y referidos en {location_focus} para recuperar las horas valle."
            )
        if target_time:
            tips.append(
                f"Publica paquetes con precio dinámico alrededor de las {target_time.strftime('%H:%M')} para equilibrar la demanda."
            )
            low_demand_tip = (
                f"Si esa franja suele moverse con poca demanda, ajusta los precios a la baja en esa ventana para llenarla y compensa con incrementos leves en las horas pico."
            )
            tips.append(low_demand_tip)
            tips.append(
                f"Aprovecha esa franja para experimentar cambios de horario pilotos: atrasa o adelanta bloques cercanos a las {target_time.strftime('%H:%M')} y observa si mejora la ocupación."
            )
        if price_focus or min_budget is not None or max_budget is not None:
            tips.append(
                "Configura promociones escalonadas (2x1, créditos de lealtad) para los presupuestos que los jugadores mencionan con más frecuencia."
            )
        if not target_time:
            tips.append(
                "Analiza los bloques de baja ocupación durante la semana y desplaza pequeños turnos en el calendario para probar otros horarios; si llenan más rápido, amplía esa ventana."
            )
        if sport_focus:
            tips.append(
                f"Reserva bloques exclusivos para {sport_focus} y comunícate con tus clientes recurrentes para anticipar disponibilidad."
            )
        tips.append(
            "Cruza feedback reciente con las canchas menos rentables y programa mantenimiento o upgrades que mejoren la experiencia."
        )
        tips.append(
            "Automatiza recordatorios de pago y libera espacios inactivos con 15 minutos de anticipación para maximizar ocupación."
        )

        campus_name_slot = tracker.get_slot("managed_campus_name")
        campus_phrase = f" en {campus_name_slot}" if campus_name_slot else ""
        response_text = (
            f"Estimado administrador, para su campus{campus_phrase} estas son algunas recomendaciones "
            "para optimizar la operación:\n"
        )
        response_text += "\n".join(f"- {tip}" for tip in tips)

        analytics_payload = {
            "response_type": "admin_recommendation",
            "tips_count": len(tips),
            "context": {
                "location": location_focus,
                "sport": sport_focus,
                "target_time": target_time.strftime("%H:%M") if target_time else None,
                "min_budget": min_budget,
                "max_budget": max_budget,
            },
        }
        response_metadata = {
            "analytics": analytics_payload,
            "recommendations": [],
        }
        dispatcher.utter_message(text=response_text, metadata=response_metadata)

        await _record_intent_and_log(
            tracker=tracker,
            session_id=session_id,
            user_id=user_id,
            response_text=response_text,
            response_type="admin_recommendation",
            message_metadata=response_metadata,
        )
        return events


class ActionProvideAdminDemandAlerts(Action):
    """Offer predictive demand alerts tailored to administrators."""

    def name(self) -> str:
        return "action_provide_admin_demand_alerts"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        latest_message = tracker.latest_message or {}
        metadata = _coerce_metadata(latest_message.get("metadata"))
        user_role = (tracker.get_slot("user_role") or metadata.get("user_role") or "player").lower()
        session_id = tracker.get_slot("chatbot_session_id")
        user_id_slot = tracker.get_slot("user_id")
        user_id = _coerce_user_identifier(user_id_slot) if user_id_slot else None

        if user_role != "admin":
            response_text = (
                "Estas alertas predictivas están disponibles solo para administradores."
            )
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=user_id,
                response_text=response_text,
                response_type="admin_demand_alerts_denied",
            )
            return []

        alerts: List[str] = []
        preferred_time = tracker.get_slot("preferred_start_time")
        target_time = _coerce_time_value(preferred_time)
        if target_time:
            formatted_time = target_time.strftime("%H:%M")
            alerts.append(
                f"- Baja ocupación detectada cerca de las {formatted_time}; considera una bajada temporal del 10-15% en esa franja."
            )
            alerts.append(
                f"- Hay señales de repunte después de las {formatted_time}; pon campañas cortas para capturar esa demanda."
            )
        else:
            alerts.append(
                "- Las franjas del mediodía de martes a jueves están consistentemente por debajo del 60% de ocupación; prueba reubicar bloques a la tarde."
            )
            alerts.append(
                "- Observamos un pico en la demanda mañanera de los fines de semana; prepara promociones o anuncios para redistribuir una parte de esa demanda."
            )

        response_text = "Alertas de demanda y ocupación:\n" + "\n".join(alerts)
        response_metadata = {
            "analytics": {
                "response_type": "admin_demand_alerts",
                "alerts": alerts,
            }
        }
        dispatcher.utter_message(text=response_text, metadata=response_metadata)

        await _record_intent_and_log(
            tracker=tracker,
            session_id=session_id,
            user_id=user_id,
            response_text=response_text,
            response_type="admin_demand_alerts",
            message_metadata=response_metadata,
        )
        return []


class ActionProvideAdminCampusTopClients(Action):
    """Return the clients who rent the most from a campus managed by the admin."""

    def name(self) -> str:
        return "action_provide_admin_campus_top_clients"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        events: List[EventType] = []
        latest_message = tracker.latest_message or {}
        metadata = _coerce_metadata(latest_message.get("metadata"))

        user_role = (tracker.get_slot("user_role") or "player").lower()
        session_id = tracker.get_slot("chatbot_session_id")
        theme = tracker.get_slot("chat_theme") or "Reservas y alquileres"

        user_id = _coerce_user_identifier(tracker.get_slot("user_id"))
        if user_id is None:
            user_id = _coerce_user_identifier(
                metadata.get("user_id") or metadata.get("id_user")
            )

        if user_role != "admin":
            response_text = (
                "Esta consulta de clientes frecuentes está reservada para administradores. "
                "Inicia sesión con el perfil de gestión para acceder a estos datos."
            )
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=user_id,
                response_text=response_text,
                response_type="admin_top_clients_denied",
                message_metadata={"role": user_role},
            )
            return events

        if user_id is None:
            response_text = (
                "No pude validar tu usuario administrador. Vuelve a iniciar sesión para revisar tus sedes."
            )
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=None,
                response_text=response_text,
                response_type="admin_top_clients_error",
            )
            return events

        if not session_id:
            try:
                ensured = await run_in_thread(
                    chatbot_service.ensure_chat_session,
                    user_id,
                    theme,
                    "admin",
                )
            except DatabaseError:
                LOGGER.exception(
                    "[ActionProvideAdminCampusTopClients] database error ensuring session for admin user_id=%s",
                    user_id,
                )
            else:
                session_id = str(ensured)
                events.append(SlotSet("chatbot_session_id", session_id))

        campus_id_slot = tracker.get_slot("managed_campus_id")
        campus_name_slot = tracker.get_slot("managed_campus_name")
        campus_context: Optional[Dict[str, Any]] = None
        if campus_id_slot:
            try:
                campus_context = {
                    "id_campus": int(campus_id_slot),
                    "name": campus_name_slot,
                }
            except ValueError:
                campus_context = None

        campuses = []
        try:
            campuses = await run_in_thread(_fetch_managed_campuses, user_id)
        except DatabaseError:
            LOGGER.exception(
                "[ActionProvideAdminCampusTopClients] database error fetching campuses for user_id=%s",
                user_id,
            )
            campuses = []

        if not campuses and campus_context:
            campuses = [campus_context]

        if campuses:
            primary = campuses[0]
            events.append(SlotSet("managed_campus_id", str(primary["id_campus"])))
            campus_name = primary.get("name")
            if campus_name:
                events.append(SlotSet("managed_campus_name", campus_name))

        if campus_context is None:
            response_text = (
                "No encuentro sedes asociadas a tu usuario administrador. "
                "Confirma en el panel de gestión que tienes un campus asignado."
            )
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=user_id,
                response_text=response_text,
                response_type="admin_top_clients_no_campus",
            )
            return events

        auth_token = _extract_token_from_metadata(metadata)
        campus_results: List[Dict[str, Any]] = []
        for campus in campuses:
            top_clients_data = await _fetch_top_clients_from_analytics(
                campus["id_campus"],
                token=auth_token,
            )
            frequent_clients: List[Dict[str, Any]] = []
            if top_clients_data:
                frequent_clients = top_clients_data.get("frequent_clients") or []
            campus_results.append(
                {
                    "campus": campus,
                    "clients": frequent_clients,
                }
            )

        if not campus_results:
            response_text = (
                "Por ahora no hay clientes frecuentes registrados para tus sedes."
            )
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=user_id,
                response_text=response_text,
                response_type="admin_top_clients_empty",
            )
            return events

        sections: List[str] = []
        metadata_clients: List[Dict[str, Any]] = []
        for result in campus_results:
            campus = result["campus"]
            campus_display = campus.get("name") or campus.get("district") or "esa sede"
            lines: List[str] = []
            if result["clients"]:
                for index, client in enumerate(result["clients"], start=1):
                    name = client.get("name") or "Cliente"
                    rent_count = client.get("rent_count") or 0
                    location = client.get("district") or client.get("city")
                    contact = client.get("phone") or client.get("email")
                    details = [f"{rent_count} rentas"]
                    if location:
                        details.append(location)
                    if contact:
                        details.append(contact)
                    else:
                        details.append("sin contacto registrado")
                    lines.append(f"{index}. {name} · {' · '.join(details)}")
            else:
                lines.append("No hay clientes frecuentes registrados por ahora.")
            sections.append(
                f"Campus {campus_display} ({len(result['clients'])} clientes frecuentes):\n"
                + "\n".join(lines)
            )
            metadata_clients.append(
                {
                    "campus_id": campus["id_campus"],
                    "campus_name": campus_display,
                    "client_count": len(result["clients"]),
                    "clients": result["clients"],
                }
            )

        response_text = (
            "Estimado administrador, aquí está el resumen consolidado de clientes frecuentes en tus campus:\n"
            + "\n\n".join(sections)
            + "\n\nSi querés, puedo profundizar en uno de ellos o preparar un reporte detallado."
        )
        response_metadata = {
            "analytics": {
                "response_type": "admin_top_clients",
                "campus_count": len(campus_results),
                "source": "analytics_service",
            },
            "top_clients": metadata_clients,
        }
        dispatcher.utter_message(text=response_text, metadata=response_metadata)
        await _record_intent_and_log(
            tracker=tracker,
            session_id=session_id,
            user_id=user_id,
            response_text=response_text,
            response_type="admin_top_clients",
            message_metadata=response_metadata,
        )
        return events


class ActionProvideAdminFieldUsage(Action):
    """Return the most used fields for the campuses managed by this admin."""

    def name(self) -> str:
        return "action_provide_admin_field_usage"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        events: List[EventType] = []
        latest_message = tracker.latest_message or {}
        metadata = _coerce_metadata(latest_message.get("metadata"))

        user_role = (tracker.get_slot("user_role") or "player").lower()
        session_id = tracker.get_slot("chatbot_session_id")
        theme = tracker.get_slot("chat_theme") or "Reservas y alquileres"

        user_id = _coerce_user_identifier(tracker.get_slot("user_id"))
        if user_id is None:
            user_id = _coerce_user_identifier(
                metadata.get("user_id") or metadata.get("id_user")
            )

        if user_role != "admin":
            response_text = (
                "Este informe está reservado para administradores. "
                "Inicia sesión con tu perfil de gestión para acceder a estos datos."
            )
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=user_id,
                response_text=response_text,
                response_type="admin_field_usage_denied",
            )
            return events

        if user_id is None:
            response_text = (
                "No identifiqué tu cuenta de administrador. Vuelve a iniciar sesión y lo revisamos."
            )
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=None,
                response_text=response_text,
                response_type="admin_field_usage_error",
            )
            return events

        if not session_id:
            try:
                ensured = await run_in_thread(
                    chatbot_service.ensure_chat_session,
                    user_id,
                    theme,
                    "admin",
                )
            except DatabaseError:
                LOGGER.exception(
                    "[ActionProvideAdminFieldUsage] database error ensuring session for admin user_id=%s",
                    user_id,
                )
            else:
                session_id = str(ensured)
                events.append(SlotSet("chatbot_session_id", session_id))

        try:
            campuses = await run_in_thread(_fetch_managed_campuses, user_id)
        except DatabaseError:
            LOGGER.exception(
                "[ActionProvideAdminFieldUsage] database error fetching campuses for user_id=%s",
                user_id,
            )
            campuses = []

        if not campuses:
            response_text = (
                "No encontré sedes asociadas a tu usuario. Confirma que estás gestionando alguna sede."
            )
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=user_id,
                response_text=response_text,
                response_type="admin_field_usage_no_campus",
            )
            return events

        result_sections: List[str] = []
        metadata_sections: List[Dict[str, Any]] = []
        auth_token = _extract_token_from_metadata(metadata)
        for campus in campuses:
            usage_data = await _fetch_field_usage_from_analytics(
                campus["id_campus"],
                token=auth_token,
            )
            fields = usage_data.get("top_fields") if usage_data else []
            section_lines: List[str] = []
            if fields:
                for index, field in enumerate(fields, start=1):
                    section_lines.append(
                        f"{index}. {field.get('field_name')} · {field.get('usage_count')} rentas"
                    )
            else:
                section_lines.append("No hay datos de uso para este campus en el mes actual.")
            campus_display = campus.get("name") or campus.get("district") or "esa sede"
            result_sections.append(
                f"Campus {campus_display} ({len(fields)} campos registrados):\n"
                + "\n".join(section_lines)
            )
            metadata_sections.append(
                {
                    "campus_id": campus["id_campus"],
                    "campus_name": campus_display,
                    "fields": fields or [],
                }
            )

        response_text = (
            "Estimado administrador, estos son los campos más usados en tus campus este mes:\n"
            + "\n\n".join(result_sections)
            + "\n\nSi querés puedo enviar este resumen por mail o profundizar uno en particular."
        )
        response_metadata = {
            "analytics": {
                "response_type": "admin_field_usage",
                "campus_count": len(campuses),
            },
            "field_usage": metadata_sections,
        }
        dispatcher.utter_message(text=response_text, metadata=response_metadata)
        await _record_intent_and_log(
            tracker=tracker,
            session_id=session_id,
            user_id=user_id,
            response_text=response_text,
            response_type="admin_field_usage",
            message_metadata=response_metadata,
        )
        return events


__all__ = [
    "ActionProvideAdminManagementTips",
    "ActionProvideAdminDemandAlerts",
    "ActionProvideAdminCampusTopClients",
    "ActionProvideAdminFieldUsage",
]
