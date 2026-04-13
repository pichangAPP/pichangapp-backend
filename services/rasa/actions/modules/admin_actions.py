from __future__ import annotations

import logging
import random
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from rasa_sdk import Action, Tracker
from rasa_sdk.events import EventType, FollowupAction, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from ..services.chatbot_service import DatabaseError, chatbot_service
from ..services.chatbot.intent_logging import record_intent_and_log as _record_intent_and_log
from ..domain.chatbot.async_utils import run_in_thread
from ..domain.chatbot.budget import (
    extract_budget_preferences as _extract_budget_preferences,
)
from ..domain.chatbot.context import (
    extract_token_from_metadata as _extract_token_from_metadata,
    resolve_secured_actor as _resolve_secured_actor,
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
    fetch_revenue_metrics_from_analytics as _fetch_revenue_metrics_from_analytics,
    fetch_top_clients_from_analytics as _fetch_top_clients_from_analytics,
)

LOGGER = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    from rapidfuzz import fuzz as _rapidfuzz_fuzz
except Exception:  # pragma: no cover - fallback path
    _rapidfuzz_fuzz = None


ADMIN_TOPIC_TO_ACTION: Dict[str, str] = {
    "metrics": "admin_metrics_form",
    "top_clients": "action_provide_admin_campus_top_clients",
    "field_usage": "action_provide_admin_field_usage",
    "demand_alerts": "action_provide_admin_demand_alerts",
    "management_tips": "action_provide_admin_management_tips",
}

ADMIN_TOPIC_LABELS: Dict[str, str] = {
    "metrics": "métricas",
    "top_clients": "clientes frecuentes",
    "field_usage": "uso de canchas",
    "demand_alerts": "alertas de demanda",
    "management_tips": "recomendaciones de gestión",
}

ADMIN_TOPIC_KEYWORDS: Dict[str, Dict[str, float]] = {
    "metrics": {
        "metrica": 1.4,
        "metricas": 1.4,
        "ingresos": 1.2,
        "ocupacion": 1.2,
        "trafico": 1.0,
        "comparativo": 1.2,
        "tendencia": 1.2,
        "ranking ingresos": 1.3,
        "esta semana": 0.4,
        "este mes": 0.4,
        "hoy": 0.3,
    },
    "top_clients": {
        "clientes frecuentes": 1.8,
        "top clientes": 1.6,
        "clientes vip": 1.6,
        "quienes rentan mas": 1.6,
        "quienes reservan mas": 1.6,
        "usuarios frecuentes": 1.4,
        "mejores clientes": 1.5,
        "clientes top": 1.5,
    },
    "field_usage": {
        "campos mas usados": 1.8,
        "canchas mas usadas": 1.8,
        "uso de canchas": 1.6,
        "uso por campo": 1.5,
        "ranking canchas": 1.5,
        "campo mas usado": 1.5,
        "top campos": 1.4,
        "campos con mas reservas": 1.5,
        "ocupacion por cancha": 1.5,
    },
    "demand_alerts": {
        "alertas": 1.4,
        "avisame": 1.3,
        "notif": 1.1,
        "notificacion": 1.2,
        "demanda": 1.4,
        "horarios vacios": 1.6,
        "baja ocupacion": 1.6,
        "turno flojo": 1.5,
        "cuando baje": 1.3,
        "cuando suba": 1.3,
    },
    "management_tips": {
        "recomendaciones": 1.5,
        "estrategias": 1.5,
        "gestion": 1.3,
        "optimizar": 1.2,
        "como mejorar": 1.4,
        "pricing dinamico": 1.8,
        "promociones": 1.2,
        "plan semanal": 1.4,
        "consejos": 1.3,
    },
}

ADMIN_CONTEXTUAL_HINTS = (
    "cuantos son",
    "cuantas son",
    "cuales son",
    "y de",
    "y ahora",
    "ahora ese",
    "ahora esa",
    "de esta semana",
    "de este mes",
    "de hoy",
    "ese dato",
    "esa data",
)


def _normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    lowered = value.strip().lower()
    normalized = unicodedata.normalize("NFD", lowered)
    without_accents = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9\s]", " ", without_accents).strip()


def _tokenize(normalized: str) -> List[str]:
    return [token for token in normalized.split() if token]


def _coerce_topic_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item in ADMIN_TOPIC_TO_ACTION]
    if isinstance(value, str) and value.strip():
        parts = [item.strip() for item in value.split(",")]
        return [item for item in parts if item in ADMIN_TOPIC_TO_ACTION]
    return []


def _fuzzy_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if _rapidfuzz_fuzz is not None:
        return float(_rapidfuzz_fuzz.ratio(left, right)) / 100.0
    return SequenceMatcher(None, left, right).ratio()


def _score_topic(
    topic: str,
    normalized_text: str,
    tokens: List[str],
    corrections: List[Dict[str, Any]],
) -> Dict[str, Any]:
    definitions = ADMIN_TOPIC_KEYWORDS.get(topic, {})
    score = 0.0
    first_pos: Optional[int] = None
    matches: List[str] = []

    for keyword, weight in definitions.items():
        if " " in keyword:
            pos = normalized_text.find(keyword)
            if pos != -1:
                score += weight
                matches.append(keyword)
                if first_pos is None or pos < first_pos:
                    first_pos = pos
            continue

        exact_positions = [idx for idx, token in enumerate(tokens) if token == keyword]
        if exact_positions:
            score += weight
            matches.append(keyword)
            if first_pos is None:
                first_pos = normalized_text.find(keyword)
            continue

        if len(keyword) < 4:
            continue

        best_token = ""
        best_ratio = 0.0
        for token in tokens:
            ratio = _fuzzy_similarity(token, keyword)
            if ratio > best_ratio:
                best_ratio = ratio
                best_token = token
        if best_ratio >= 0.86:
            score += weight * 0.7
            matches.append(keyword)
            corrections.append(
                {
                    "topic": topic,
                    "typed": best_token,
                    "matched": keyword,
                    "ratio": round(best_ratio, 3),
                }
            )
            token_pos = normalized_text.find(best_token)
            if token_pos != -1 and (first_pos is None or token_pos < first_pos):
                first_pos = token_pos

    return {
        "topic": topic,
        "score": score,
        "first_pos": first_pos if first_pos is not None else 10_000,
        "matches": matches,
    }


def _is_contextual_followup(normalized_text: str) -> bool:
    if not normalized_text:
        return False
    if any(hint in normalized_text for hint in ADMIN_CONTEXTUAL_HINTS):
        return True
    token_count = len(normalized_text.split())
    return token_count <= 3 and normalized_text in {"si", "ok", "dale", "esa", "ese", "eso"}


def _extract_routing_context(tracker: Tracker) -> Dict[str, Any]:
    return {
        "topic_detected": tracker.get_slot("admin_topic_detected"),
        "last_topic": tracker.get_slot("admin_last_topic"),
        "pending_topics": _coerce_topic_list(tracker.get_slot("admin_topics_pending")),
        "confidence": tracker.get_slot("routing_confidence"),
        "reason": tracker.get_slot("admin_routing_reason"),
        "corrections": tracker.get_slot("admin_routing_corrections") or [],
    }


def _topic_label(topic: Optional[str]) -> str:
    if not topic:
        return "ese tema"
    return ADMIN_TOPIC_LABELS.get(topic, topic)


class ActionRouteAdminRequest(Action):
    """Deterministic router for admin requests with keyword and fuzzy matching."""

    def name(self) -> str:
        return "action_route_admin_request"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        del domain
        events: List[EventType] = []
        latest_message = tracker.latest_message or {}
        actor = _resolve_secured_actor(
            tracker, latest_message.get("metadata"), for_admin_action=True
        )
        session_id = tracker.get_slot("chatbot_session_id")
        user_id = actor.user_id

        if not actor.admin_authorized:
            response_text = (
                "Ese flujo está reservado para administradores. "
                "Si necesitas buscar canchas como jugador, te ayudo de inmediato."
            )
            dispatcher.utter_message(response="utter_admin_only_flow")
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=user_id,
                response_text=response_text,
                response_type="admin_router_denied",
                message_metadata={
                    "routing": {
                        "reason": "non_admin_user"
                        if actor.token_valid
                        else "missing_or_invalid_jwt",
                    }
                },
            )
            return events

        text = latest_message.get("text") or ""
        normalized = _normalize_text(text)
        tokens = _tokenize(normalized)

        previous_last_topic = tracker.get_slot("admin_last_topic")
        pending_topics = _coerce_topic_list(tracker.get_slot("admin_topics_pending"))

        corrections: List[Dict[str, Any]] = []
        scored: List[Dict[str, Any]] = []
        for topic in ADMIN_TOPIC_TO_ACTION:
            scored.append(_score_topic(topic, normalized, tokens, corrections))

        scored.sort(key=lambda item: (-item["score"], item["first_pos"]))
        detected = [item for item in scored if item["score"] >= 1.0]
        detected.sort(key=lambda item: (item["first_pos"], -item["score"]))
        detected_topics = [item["topic"] for item in detected]

        selected_topic: Optional[str] = None
        selected_score = 0.0
        selected_matches: List[str] = []
        new_pending: List[str] = []
        routing_reason = "no_topic_detected"

        if detected_topics:
            selected_topic = detected_topics[0]
            top_item = next(item for item in detected if item["topic"] == selected_topic)
            selected_score = float(top_item["score"])
            selected_matches = list(top_item.get("matches") or [])

            explicit_remaining = [topic for topic in detected_topics[1:] if topic != selected_topic]
            carry_over = [
                topic for topic in pending_topics if topic != selected_topic and topic not in explicit_remaining
            ]
            new_pending = explicit_remaining + carry_over
            routing_reason = "keyword_match"
        elif pending_topics:
            selected_topic = pending_topics[0]
            new_pending = pending_topics[1:]
            selected_score = 1.0
            routing_reason = "pending_queue"
        elif previous_last_topic and _is_contextual_followup(normalized):
            selected_topic = previous_last_topic
            selected_score = 0.9
            routing_reason = "contextual_followup"

        confidence = round(min(0.99, 0.35 + (selected_score * 0.2)), 4) if selected_topic else 0.0
        routing_payload = {
            "response_type": "admin_router",
            "selected_topic": selected_topic,
            "detected_topics": detected_topics,
            "pending_topics": new_pending,
            "confidence": confidence,
            "reason": routing_reason,
            "matches": selected_matches,
            "corrections": corrections[:5],
        }

        events.extend(
            [
                SlotSet("admin_topic_detected", selected_topic),
                SlotSet("admin_topics_pending", new_pending),
                SlotSet("routing_confidence", confidence),
                SlotSet("admin_routing_reason", routing_reason),
                SlotSet("admin_routing_corrections", corrections[:5]),
            ]
        )
        if selected_topic:
            events.append(SlotSet("admin_last_topic", selected_topic))

        if not selected_topic:
            clarify_options = (
                "Puedo ayudarte con métricas, clientes frecuentes, uso de canchas, alertas de demanda o consejos de gestión.",
                "¿Deseas métricas, clientes frecuentes, uso de canchas, alertas de demanda o recomendaciones de gestión?",
                "No me quedó claro el tema admin. Dime si revisamos métricas, clientes, uso de canchas, alertas o gestión.",
            )
            response_text = random.choice(clarify_options)
            dispatcher.utter_message(
                text=response_text,
                metadata={
                    "response_type": "admin_router_clarify",
                    "routing": routing_payload,
                },
            )
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=user_id,
                response_text=response_text,
                response_type="admin_router_clarify",
                message_metadata={"routing": routing_payload},
            )
            return events

        target_action = ADMIN_TOPIC_TO_ACTION[selected_topic]
        return events + [FollowupAction(target_action)]


class ActionAdminPostTopicFollowup(Action):
    """Generate contextual admin follow-up using routed topic and pending queue."""

    def name(self) -> str:
        return "action_admin_post_topic_followup"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        del domain
        latest_message = tracker.latest_message or {}
        actor = _resolve_secured_actor(
            tracker, latest_message.get("metadata"), for_admin_action=True
        )
        metadata = actor.enriched_metadata
        session_id = tracker.get_slot("chatbot_session_id")
        user_id = actor.user_id

        if not actor.admin_authorized:
            return []

        current_topic = tracker.get_slot("admin_topic_detected") or tracker.get_slot("admin_last_topic")
        pending_topics = _coerce_topic_list(tracker.get_slot("admin_topics_pending"))

        if pending_topics:
            next_topic = pending_topics[0]
            suggestions = (
                f"También detecté una consulta sobre {_topic_label(next_topic)}. ¿Seguimos con eso ahora?",
                f"Si quieres, continúo con {_topic_label(next_topic)} en el siguiente mensaje.",
                f"Tengo pendiente {_topic_label(next_topic)}. ¿Lo revisamos de una vez?",
            )
            response_text = random.choice(suggestions)
        elif current_topic:
            options = (
                f"¿Quieres cambiar a otro tema admin? Puedo ver métricas, clientes frecuentes, uso de canchas, alertas o gestión.",
                f"Si deseas, ahora revisamos otro frente: métricas, clientes, uso de canchas, alertas o recomendaciones de gestión.",
                f"¿Te ayudo con algo más de administración? Tengo disponibles métricas, clientes, uso de canchas, alertas y gestión.",
            )
            response_text = random.choice(options)
        else:
            response_text = (
                "¿Deseas revisar métricas, clientes frecuentes, uso de canchas, alertas de demanda o recomendaciones de gestión?"
            )

        followup_metadata = {
            "response_type": "admin_followup",
            "followup": {
                "current_topic": current_topic,
                "pending_topics": pending_topics,
                "next_topic": pending_topics[0] if pending_topics else None,
            },
            "routing": _extract_routing_context(tracker),
        }
        dispatcher.utter_message(text=response_text, metadata=followup_metadata)

        await _record_intent_and_log(
            tracker=tracker,
            session_id=session_id,
            user_id=user_id,
            response_text=response_text,
            response_type="admin_followup",
            message_metadata=followup_metadata,
        )
        return []


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
        events.extend(
            [
                SlotSet("admin_last_topic", "management_tips"),
                SlotSet("admin_topic_detected", "management_tips"),
            ]
        )
        latest_message = tracker.latest_message or {}
        theme = tracker.get_slot("chat_theme") or "Reservas y alquileres"
        session_id = tracker.get_slot("chatbot_session_id")
        actor = _resolve_secured_actor(
            tracker, latest_message.get("metadata"), for_admin_action=True
        )
        metadata = actor.enriched_metadata
        user_id = actor.user_id

        if not actor.admin_authorized:
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
            "response_type": "admin_recommendation",
            "analytics": analytics_payload,
            "recommendations": [],
            "routing": _extract_routing_context(tracker),
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
        events: List[EventType] = [
            SlotSet("admin_last_topic", "demand_alerts"),
            SlotSet("admin_topic_detected", "demand_alerts"),
        ]
        latest_message = tracker.latest_message or {}
        actor = _resolve_secured_actor(
            tracker, latest_message.get("metadata"), for_admin_action=True
        )
        metadata = actor.enriched_metadata
        session_id = tracker.get_slot("chatbot_session_id")
        user_id = actor.user_id

        if not actor.admin_authorized:
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
            return events

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
            "response_type": "admin_demand_alerts",
            "analytics": {
                "response_type": "admin_demand_alerts",
                "alerts": alerts,
            },
            "routing": _extract_routing_context(tracker),
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
        return events


class ActionProvideAdminMetrics(Action):
    """Provide conversational admin metrics (income, occupancy, traffic, etc.)."""

    def name(self) -> str:
        return "action_provide_admin_metrics"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        events: List[EventType] = []
        events.extend(
            [
                SlotSet("admin_last_topic", "metrics"),
                SlotSet("admin_topic_detected", "metrics"),
            ]
        )
        latest_message = tracker.latest_message or {}
        theme = tracker.get_slot("chat_theme") or "Reservas y alquileres"
        actor = _resolve_secured_actor(
            tracker, latest_message.get("metadata"), for_admin_action=True
        )
        metadata = actor.enriched_metadata
        session_id = tracker.get_slot("chatbot_session_id")
        user_id = actor.user_id

        if not actor.admin_authorized:
            response_text = (
                "Estas métricas están disponibles solo para administradores. "
                "Si necesitas reservar una cancha, dime qué buscas y te ayudo."
            )
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=user_id,
                response_text=response_text,
                response_type="admin_metrics_denied",
            )
            return events

        if user_id is None:
            response_text = (
                "No pude validar tu usuario administrador. Vuelve a iniciar sesión para revisar tus métricas."
            )
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=None,
                response_text=response_text,
                response_type="admin_metrics_error",
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
                    "[ActionProvideAdminMetrics] database error ensuring session for admin user_id=%s",
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

        campuses: List[Dict[str, Any]] = []
        try:
            campuses = await run_in_thread(_fetch_managed_campuses, user_id)
        except DatabaseError:
            LOGGER.exception(
                "[ActionProvideAdminMetrics] database error fetching campuses for user_id=%s",
                user_id,
            )
            response_text = (
                "No pude consultar tus sedes por un problema temporal en la base de datos. "
                "Intenta nuevamente en unos segundos."
            )
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=user_id,
                response_text=response_text,
                response_type="admin_metrics_db_error",
            )
            return events

        if not campuses and campus_context:
            campuses = [campus_context]

        if campuses:
            primary = campuses[0]
            events.append(SlotSet("managed_campus_id", str(primary["id_campus"])))
            campus_name = primary.get("name")
            if campus_name:
                events.append(SlotSet("managed_campus_name", campus_name))

        if campus_context is None and campuses:
            campus_context = campuses[0]

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
                response_type="admin_metrics_no_campus",
            )
            return events

        metric_type = (tracker.get_slot("admin_metric_type") or "ingresos").lower()
        metric_period = (tracker.get_slot("admin_metric_period") or "semana").lower()
        auth_token = _extract_token_from_metadata(metadata)

        response_text = ""
        response_metadata: Dict[str, Any] = {
            "response_type": "admin_metrics",
            "analytics": {
                "metric_type": metric_type,
                "metric_period": metric_period,
                "campus_id": campus_context.get("id_campus"),
                "campus_name": campus_context.get("name"),
                "source": "analytics_service",
            },
            "routing": _extract_routing_context(tracker),
        }

        if metric_type in {"clientes", "client", "clientes_frecuentes"}:
            top_clients = await _fetch_top_clients_from_analytics(
                campus_context["id_campus"],
                token=auth_token,
            )
            frequent_clients = (top_clients or {}).get("frequent_clients") or []
            if not frequent_clients:
                response_text = "Aún no hay clientes frecuentes registrados para esta sede."
            else:
                top_lines = []
                for idx, client in enumerate(frequent_clients[:5], start=1):
                    name = client.get("name") or "Cliente"
                    rents = client.get("rent_count") or 0
                    top_lines.append(f"{idx}. {name} ({rents} reservas)")
                response_text = (
                    f"Clientes frecuentes en {campus_context.get('name') or 'tu sede'}:\\n"
                    + "\\n".join(top_lines)
                )
                response_metadata["analytics"]["clients"] = frequent_clients[:5]
        elif metric_type in {"canchas", "campos", "fields"}:
            usage = await _fetch_field_usage_from_analytics(
                campus_context["id_campus"],
                token=auth_token,
            )
            fields = (usage or {}).get("fields") or []
            if not fields:
                response_text = "Aún no hay datos de uso de canchas para esta sede."
            else:
                lines = []
                for idx, field in enumerate(fields[:5], start=1):
                    name = field.get("field_name") or field.get("name") or "Cancha"
                    rents = field.get("rent_count") or field.get("total_rents") or 0
                    lines.append(f"{idx}. {name} ({rents} rentas)")
                response_text = (
                    f"Canchas más usadas en {campus_context.get('name') or 'tu sede'}:\\n"
                    + "\\n".join(lines)
                )
                response_metadata["analytics"]["fields"] = fields[:5]
        elif metric_type in {"comparativo"}:
            period_label = "esta semana"
            if metric_period in {"hoy", "dia", "today"}:
                period_label = "hoy"
            elif metric_period in {"mes", "mensual", "month"}:
                period_label = "este mes"

            if len(campuses) < 2:
                response_text = (
                    "Solo encontré una sede asociada, así que no puedo generar un comparativo todavía."
                )
            else:
                comparisons: List[Dict[str, Any]] = []
                for campus in campuses:
                    metrics = await _fetch_revenue_metrics_from_analytics(
                        campus["id_campus"],
                        token=auth_token,
                    )
                    if not metrics:
                        continue
                    if metric_period in {"hoy", "dia", "today"}:
                        amount = metrics.get("today_income_total")
                    elif metric_period in {"mes", "mensual", "month"}:
                        amount = metrics.get("monthly_income_total")
                    else:
                        amount = metrics.get("weekly_income_total")
                    fields = metrics.get("fields") or {}
                    available = fields.get("available")
                    total = fields.get("total")
                    occupancy_pct = None
                    if available is not None and total not in (None, 0):
                        occupied = max(int(total) - int(available), 0)
                        occupancy_pct = (occupied / int(total)) * 100 if total else 0
                    comparisons.append(
                        {
                            "campus_id": campus["id_campus"],
                            "campus_name": metrics.get("campus_name") or campus.get("name"),
                            "amount": amount,
                            "occupancy_pct": occupancy_pct,
                            "available": available,
                            "total": total,
                        }
                    )

                if not comparisons:
                    response_text = "No tengo datos suficientes para comparar tus sedes."
                else:
                    comparisons.sort(key=lambda item: (item.get("amount") or 0), reverse=True)
                    lines = []
                    for idx, item in enumerate(comparisons[:5], start=1):
                        occ_text = ""
                        if item.get("occupancy_pct") is not None:
                            occ_text = f", ocupación {item['occupancy_pct']:.0f}%"
                        lines.append(
                            f"{idx}. {item.get('campus_name') or 'Sede'}: S/ {item.get('amount')}{occ_text}"
                        )
                    response_text = (
                        f"Comparativo de ingresos {period_label}:\n" + "\n".join(lines)
                    )
                    response_metadata["analytics"]["comparisons"] = comparisons
        elif metric_type in {"tendencia"}:
            metrics = await _fetch_revenue_metrics_from_analytics(
                campus_context["id_campus"],
                token=auth_token,
            )
            if not metrics:
                response_text = "No pude obtener métricas en este momento. Intenta nuevamente en unos minutos."
            else:
                campus_name = metrics.get("campus_name") or campus_context.get("name") or "tu sede"
                traffic = metrics.get("last_seven_days_rent_traffic") or []
                income_series = metrics.get("weekly_daily_income") or []
                response_parts = []

                if traffic and len(traffic) >= 2:
                    first = traffic[0].get("rent_count", 0)
                    last = traffic[-1].get("rent_count", 0)
                    direction = "estable"
                    if last > first:
                        direction = "al alza"
                    elif last < first:
                        direction = "a la baja"
                    response_parts.append(
                        f"El tráfico de reservas va {direction}: pasó de {first} a {last} rentas en 7 días."
                    )

                if income_series and len(income_series) >= 2:
                    def _to_float(value: Any) -> float:
                        try:
                            return float(value)
                        except (TypeError, ValueError):
                            return 0.0

                    first_amount = _to_float(income_series[0].get("total_amount"))
                    last_amount = _to_float(income_series[-1].get("total_amount"))
                    direction = "estable"
                    if last_amount > first_amount:
                        direction = "al alza"
                    elif last_amount < first_amount:
                        direction = "a la baja"
                    response_parts.append(
                        f"Los ingresos diarios van {direction}: de S/ {first_amount:.0f} a S/ {last_amount:.0f}."
                    )

                if not response_parts:
                    response_text = f"No tengo datos suficientes para mostrar tendencia en {campus_name}."
                else:
                    response_text = f"Tendencias recientes en {campus_name}: " + " ".join(response_parts)
                    response_metadata["analytics"]["traffic"] = traffic
                    response_metadata["analytics"]["weekly_income"] = income_series
        else:
            metrics = await _fetch_revenue_metrics_from_analytics(
                campus_context["id_campus"],
                token=auth_token,
            )
            if not metrics:
                response_text = "No pude obtener métricas en este momento. Intenta nuevamente en unos minutos."
            else:
                campus_name = metrics.get("campus_name") or campus_context.get("name") or "tu sede"
                if metric_type in {"ingresos", "revenue", "income"}:
                    if metric_period in {"hoy", "dia", "today"}:
                        amount = metrics.get("today_income_total")
                        period_label = "hoy"
                    elif metric_period in {"mes", "mensual", "month"}:
                        amount = metrics.get("monthly_income_total")
                        period_label = "este mes"
                    else:
                        amount = metrics.get("weekly_income_total")
                        period_label = "esta semana"
                    response_text = (
                        f"En {campus_name}, los ingresos {period_label} son aproximadamente S/ {amount}."
                    )
                    response_metadata["analytics"]["amount"] = amount
                elif metric_type in {"ocupacion", "ocupación", "availability"}:
                    fields = metrics.get("fields") or {}
                    available = fields.get("available")
                    total = fields.get("total")
                    if available is None or total in (None, 0):
                        response_text = (
                            f"En {campus_name}, no tengo datos suficientes para calcular la ocupación."
                        )
                    else:
                        occupied = max(int(total) - int(available), 0)
                        occupancy_pct = (occupied / int(total)) * 100 if total else 0
                        response_text = (
                            f"En {campus_name}, hay {available} de {total} canchas disponibles. "
                            f"La ocupación estimada es {occupancy_pct:.0f}%."
                        )
                        response_metadata["analytics"]["availability"] = {
                            "available": available,
                            "total": total,
                            "occupied": occupied,
                            "occupancy_pct": occupancy_pct,
                        }
                else:
                    traffic = metrics.get("last_seven_days_rent_traffic") or []
                    if not traffic:
                        response_text = (
                            f"No tengo datos de tráfico de rentas recientes para {campus_name}."
                        )
                    else:
                        total_rents = sum(item.get("rent_count", 0) for item in traffic)
                        avg_rents = total_rents / len(traffic) if traffic else 0
                        response_text = (
                            f"En {campus_name}, el tráfico de rentas de los últimos 7 días es "
                            f"{total_rents} en total (promedio {avg_rents:.1f} por día)."
                        )
                        response_metadata["analytics"]["traffic"] = traffic

        dispatcher.utter_message(text=response_text, metadata=response_metadata)
        await _record_intent_and_log(
            tracker=tracker,
            session_id=session_id,
            user_id=user_id,
            response_text=response_text,
            response_type="admin_metrics",
            message_metadata=response_metadata,
        )
        return events

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
        events.extend(
            [
                SlotSet("admin_last_topic", "top_clients"),
                SlotSet("admin_topic_detected", "top_clients"),
            ]
        )
        latest_message = tracker.latest_message or {}
        actor = _resolve_secured_actor(
            tracker, latest_message.get("metadata"), for_admin_action=True
        )
        metadata = actor.enriched_metadata

        session_id = tracker.get_slot("chatbot_session_id")
        theme = tracker.get_slot("chat_theme") or "Reservas y alquileres"

        user_id = actor.user_id

        if not actor.admin_authorized:
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
                message_metadata={"role": actor.role},
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
            response_text = (
                "No pude consultar tus sedes por un problema temporal en la base de datos. "
                "Intenta nuevamente en unos segundos."
            )
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=user_id,
                response_text=response_text,
                response_type="admin_top_clients_db_error",
            )
            return events

        if not campuses and campus_context:
            campuses = [campus_context]

        if campuses:
            primary = campuses[0]
            events.append(SlotSet("managed_campus_id", str(primary["id_campus"])))
            campus_name = primary.get("name")
            if campus_name:
                events.append(SlotSet("managed_campus_name", campus_name))
            if campus_context is None:
                campus_context = primary

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
            "response_type": "admin_top_clients",
            "analytics": {
                "response_type": "admin_top_clients",
                "campus_count": len(campus_results),
                "source": "analytics_service",
            },
            "top_clients": metadata_clients,
            "routing": _extract_routing_context(tracker),
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
        events.extend(
            [
                SlotSet("admin_last_topic", "field_usage"),
                SlotSet("admin_topic_detected", "field_usage"),
            ]
        )
        latest_message = tracker.latest_message or {}
        actor = _resolve_secured_actor(
            tracker, latest_message.get("metadata"), for_admin_action=True
        )
        metadata = actor.enriched_metadata

        session_id = tracker.get_slot("chatbot_session_id")
        theme = tracker.get_slot("chat_theme") or "Reservas y alquileres"

        user_id = actor.user_id

        if not actor.admin_authorized:
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
            response_text = (
                "No pude consultar tus sedes por un problema temporal en la base de datos. "
                "Intenta nuevamente en unos segundos."
            )
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=user_id,
                response_text=response_text,
                response_type="admin_field_usage_db_error",
            )
            return events

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
            "response_type": "admin_field_usage",
            "analytics": {
                "response_type": "admin_field_usage",
                "campus_count": len(campuses),
            },
            "field_usage": metadata_sections,
            "routing": _extract_routing_context(tracker),
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
    "ActionRouteAdminRequest",
    "ActionAdminPostTopicFollowup",
    "ActionProvideAdminManagementTips",
    "ActionProvideAdminDemandAlerts",
    "ActionProvideAdminMetrics",
    "ActionProvideAdminCampusTopClients",
    "ActionProvideAdminFieldUsage",
]
