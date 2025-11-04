"""Custom actions for booking recommendations and analytics integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import Any, Dict, Iterable, List, Optional

from rasa_sdk import Action, Tracker
from rasa_sdk.events import ActionExecuted, EventType, SessionStarted, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from .infrastructure.security import (
    TokenDecodeError,
    decode_access_token,
    extract_role_from_claims,
)
from .models import FieldRecommendation
from .services.chatbot_service import DatabaseError, chatbot_service

LOGGER = logging.getLogger(__name__)


async def run_in_thread(function: Any, *args: Any, **kwargs: Any) -> Any:
    loop = asyncio.get_running_loop()
    bound = partial(function, *args, **kwargs)
    return await loop.run_in_executor(None, bound)

def _coerce_metadata(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _normalize_role_from_metadata(metadata: Dict[str, Any]) -> Optional[str]:
    raw_role = metadata.get("user_role") or metadata.get("role")
    if isinstance(raw_role, str):
        lowered = raw_role.strip().lower()
        if lowered in {"admin", "player"}:
            return lowered
        try:
            numeric = int(lowered)
            if numeric == 2:
                return "admin"
            if numeric == 1:
                return "player"
        except ValueError:
            pass
    elif raw_role is not None:
        try:
            numeric = int(raw_role)
            if numeric == 2:
                return "admin"
            if numeric == 1:
                return "player"
        except (TypeError, ValueError):
            pass

    role_id = metadata.get("id_role")
    if role_id is not None:
        try:
            numeric = int(role_id)
            if numeric == 2:
                return "admin"
            if numeric == 1:
                return "player"
        except (TypeError, ValueError):
            return None

    return metadata.get("default_role") if metadata.get("default_role") in {"admin", "player"} else None


def _extract_token_from_metadata(metadata: Dict[str, Any]) -> Optional[str]:
    candidates = [
        metadata.get("token"),
        metadata.get("access_token"),
        metadata.get("auth_token"),
        metadata.get("authorization"),
        metadata.get("Authorization"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate

    headers = metadata.get("headers")
    if isinstance(headers, dict):
        header_token = headers.get("Authorization") or headers.get("authorization")
        if isinstance(header_token, str) and header_token.strip():
            return header_token

    return None


def _enrich_metadata_with_token(metadata: Dict[str, Any]) -> Dict[str, Any]:
    token = _extract_token_from_metadata(metadata)
    if not token:
        return metadata

    try:
        claims = decode_access_token(token)
    except TokenDecodeError:
        LOGGER.warning("[Token] Unable to decode token from metadata", exc_info=True)
        return metadata

    metadata.setdefault("token_claims", claims)

    user_identifier = claims.get("id_user") or claims.get("sub")
    if user_identifier is not None and "id_user" not in metadata:
        try:
            metadata["id_user"] = int(user_identifier)
        except (TypeError, ValueError):
            metadata["id_user"] = user_identifier

    if "user_id" not in metadata and "id_user" in metadata:
        metadata["user_id"] = metadata["id_user"]

    if "id_role" not in metadata and "id_role" in claims:
        metadata["id_role"] = claims["id_role"]

    role_name = extract_role_from_claims(claims)
    if role_name:
        metadata.setdefault("role", role_name)
        metadata.setdefault("user_role", role_name)
        metadata.setdefault("default_role", role_name)

    return metadata


def _slot_already_planned(events: Iterable[EventType], slot_name: str) -> bool:
    for event in events:
        if hasattr(event, "key") and getattr(event, "key") == slot_name:
            return True
        if hasattr(event, "name") and getattr(event, "name") == slot_name:
            event_type = getattr(event, "event", None)
            if event_type == "slot":
                return True
        if isinstance(event, dict):
            event_type = event.get("event") or event.get("type")
            slot_key = event.get("name") or event.get("slot")
            if event_type == "slot" and slot_key == slot_name:
                return True
    return False

def _slot_defined(slot_name: str, domain: DomainDict) -> bool:
    """Return True if the slot exists in the loaded domain."""

    if domain is None:
        return False

    # DomainDict is a Mapping[str, Any] in the action server. Slots can be
    # exposed either as a mapping (common in production servers) or a list of
    # descriptor dictionaries (when the server serialises the domain).
    slots: Any = None

    if hasattr(domain, "as_dict") and callable(getattr(domain, "as_dict")):
        try:
            domain_dict = domain.as_dict()
        except Exception:  # pragma: no cover - defensive
            domain_dict = None
        else:
            slots = domain_dict.get("slots")
            if isinstance(slots, dict):
                return slot_name in slots
            if isinstance(slots, list):
                for slot in slots:
                    if isinstance(slot, dict) and slot.get("name") == slot_name:
                        return True
                # fall through to inspect any other representation

    if isinstance(domain, dict):
        slots = domain.get("slots")
    else:  # pragma: no cover - fallback for Domain objects
        try:
            slots = getattr(domain, "slots")
        except AttributeError:
            slots = None
        if slots is None:
            try:
                slot_names = getattr(domain, "slot_names")
            except AttributeError:
                slot_names = None
            else:
                if callable(slot_names):
                    try:
                        names = slot_names()
                    except TypeError:
                        names = list(slot_names)
                else:
                    names = slot_names
                if isinstance(names, Iterable) and slot_name in names:
                    return True

    if isinstance(slots, dict):
        return slot_name in slots
    if isinstance(slots, list):
        for slot in slots:
            if isinstance(slot, dict):
                name = slot.get("name") or slot.get("slot_name")
            else:
                name = getattr(slot, "name", None)
            if name == slot_name:
                return True

    return False


def _slot_already_planned(events: Iterable[EventType], slot_name: str) -> bool:
    for event in events:
        if hasattr(event, "key") and getattr(event, "key") == slot_name:
            return True
        if hasattr(event, "name") and getattr(event, "name") == slot_name:
            event_type = getattr(event, "event", None)
            if event_type == "slot":
                return True
        if isinstance(event, dict):
            event_type = event.get("event") or event.get("type")
            slot_key = event.get("name") or event.get("slot")
            if event_type == "slot" and slot_key == slot_name:
                return True
    return False


def _coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(value, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
    return datetime.now(timezone.utc)


def _parse_datetime(date_value: Optional[str], time_value: Optional[str]) -> datetime:
    if date_value:
        try:
            date_part = datetime.fromisoformat(date_value)
        except ValueError:
            date_part = datetime.strptime(date_value, "%Y-%m-%d")
    else:
        date_part = datetime.now(timezone.utc)

    if date_part.tzinfo is None:
        date_part = date_part.replace(tzinfo=timezone.utc)

    if time_value:
        try:
            time_part = datetime.fromisoformat(time_value)
        except ValueError:
            time_part = datetime.strptime(time_value, "%H:%M")
        if time_part.tzinfo:
            date_part = date_part.astimezone(time_part.tzinfo)
        date_part = date_part.replace(
            hour=time_part.hour,
            minute=time_part.minute,
            second=0,
            microsecond=0,
        )
    return date_part

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
            latest_metadata,
        )

        if not user_id_raw:
            dispatcher.utter_message(
                text=(
                    "No pude identificar tu usuario desde las credenciales. "
                    "Vuelve a iniciar sesión y retomamos la búsqueda de canchas."
                ),
            )
            return []

        try:
            user_id = int(str(user_id_raw).strip())
        except ValueError:
            dispatcher.utter_message(
                text=(
                    "Parece que tu sesión no trae un usuario válido. "
                    "Prueba iniciando sesión otra vez y te ayudo con la reserva."
                )
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
            dispatcher.utter_message(
                text=(
                    "En este momento no puedo conectarme a la base de datos para revisar las canchas. "
                    "Inténtalo de nuevo en unos minutos."
                )
            )
            return []

        preferred_sport = tracker.get_slot("preferred_sport")
        preferred_surface = tracker.get_slot("preferred_surface")
        preferred_location = tracker.get_slot("preferred_location")
        preferred_date = tracker.get_slot("preferred_date")
        preferred_start_time = tracker.get_slot("preferred_start_time")
        preferred_end_time = tracker.get_slot("preferred_end_time")

        try:
            recommendations: List[FieldRecommendation] = await run_in_thread(
                chatbot_service.fetch_field_recommendations,
                sport=preferred_sport,
                surface=preferred_surface,
                location=preferred_location,
                limit=3,
            )
        except DatabaseError:
            dispatcher.utter_message(
                text=(
                    "No pude consultar las canchas disponibles en este momento. "
                    "Por favor, intenta de nuevo más tarde."
                )
            )
            return [SlotSet("chatbot_session_id", str(session_id))]

        if not recommendations:
            LOGGER.warning(
                "[ActionSubmitFieldRecommendationForm] no recommendations found for session=%s user_id=%s",
                session_id,
                user_id,
            )
            dispatcher.utter_message(
                text=(
                    "No encontré canchas que coincidan con tus preferencias. "
                    "¿Te gustaría que revise otras zonas u horarios?"
                )
            )
            return [SlotSet("chatbot_session_id", str(session_id))]

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
            if user_role == "admin":
                line = (
                    f"{idx}. {rec.field_name} en {rec.campus_name} ({rec.district}). "
                    f"Disciplina: {rec.sport_name}. Superficie: {rec.surface}. "
                    f"Capacidad: {rec.capacity} jugadores. Tarifa referencial S/ {rec.price_per_hour:.2f} por hora."
                )
            else:
                line = (
                    f"{idx}. {rec.field_name} en {rec.campus_name} ({rec.district}). "
                    f"Ideal para tu partido de {rec.sport_name} en superficie {rec.surface}. "
                    f"Tiene espacio para {rec.capacity} jugadores y la hora está alrededor de S/ {rec.price_per_hour:.2f}."
                )
            summary_lines.append(line)

        if user_role == "admin":
            intro = "Estas son las alternativas que mejor se ajustan a su equipo:"
            closing = "Si requiere coordinar disponibilidad extra o apoyo con la gestión, avíseme."
        else:
            intro = "Aquí tienes opciones que se ajustan a lo que buscas para tu partido:"
            closing = "Si quieres que reserve alguna opción o busque algo distinto, solo dime."

        response_text = f"{intro}\n" + "\n".join(summary_lines) + f"\n{closing}"
        dispatcher.utter_message(text=response_text)

        try:
            await run_in_thread(
                chatbot_service.log_chatbot_message,
                session_id=session_id,
                intent_id=None,
                recommendation_id=None,
                message_text=user_message,
                bot_response="",
                response_type="user_message",
                sender_type="user",
                user_id=user_id,
                metadata=latest_metadata,
                intent_confidence=None,
            )
            LOGGER.debug(
                "[ActionSubmitFieldRecommendationForm] logged user message for session=%s",
                session_id,
            )

            recommendation_id = await run_in_thread(
                chatbot_service.create_recommendation_log,
                status="suggested",
                message=summary_lines[0],
                suggested_start=start_dt,
                suggested_end=end_dt,
                field_id=top_choice.id_field,
                user_id=user_id,
            )
            LOGGER.info(
                "[ActionSubmitFieldRecommendationForm] stored recommendation id=%s for session=%s",
                recommendation_id,
                session_id,
            )

            intent_data = tracker.latest_message.get("intent") or {}
            intent_name = intent_data.get("name") or "request_field_recommendation"
            confidence = intent_data.get("confidence")
            source_model = latest_metadata.get("model") or latest_metadata.get("pipeline")

            intent_id = await run_in_thread(
                chatbot_service.ensure_intent,
                intent_name=intent_name,
                example_phrases=[user_message or intent_name],
                response_template=response_text,
                confidence=confidence,
                detected=bool(intent_name),
                false_positive=False,
                source_model=source_model,
            )
            LOGGER.info(
                "[ActionSubmitFieldRecommendationForm] intent ensured id=%s name=%s session=%s",
                intent_id,
                intent_name,
                session_id,
            )

            # registra el intercambio completo
            await run_in_thread(
                chatbot_service.log_chatbot_message,
                session_id=session_id,
                intent_id=intent_id,
                recommendation_id=recommendation_id,
                message_text=response_text,
                bot_response=response_text,
                response_type="recommendation",
                sender_type="bot",
                user_id=user_id,
                intent_confidence=confidence,
                metadata={**latest_metadata, "detected_intent": intent_name},
            )
            LOGGER.debug(
                "[ActionSubmitFieldRecommendationForm] logged recommendation response for session=%s",
                session_id,
            )

        except DatabaseError:
            LOGGER.exception(
                "[ActionSubmitFieldRecommendationForm] database error persisting analytics for session=%s",
                session_id,
            )

        events: List[EventType] = [
            SlotSet("chatbot_session_id", str(session_id)),
            SlotSet("preferred_end_time", preferred_end_time or end_dt.isoformat()),
        ]
        return events


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
            dispatcher.utter_message(
                text=(
                    "No encuentro tu usuario activo. Inicia sesión nuevamente para revisar tu historial."
                )
            )
            return []

        try:
            user_id = int(str(user_id_raw).strip())
        except ValueError:
            dispatcher.utter_message(
                text="Necesito que vuelvas a iniciar sesión para identificarte correctamente."
            )
            return []

        if not session_id:
            try:
                session_id = await run_in_thread(
                    chatbot_service.ensure_chat_session,
                    user_id,
                    tracker.get_slot("chat_theme") or "Reservas y alquileres",
                    user_role,
                )
                events.append(SlotSet("chatbot_session_id", str(session_id)))
            except DatabaseError:
                dispatcher.utter_message(
                    text="No logré conectar con el historial en este momento. Intenta nuevamente en unos minutos."
                )
                return events

        try:
            history = await run_in_thread(
                chatbot_service.fetch_recommendation_history,
                int(session_id),
                3,
            )
        except DatabaseError:
            dispatcher.utter_message(
                text="No pude revisar el historial de recomendaciones en este momento. Intenta luego, por favor.",
            )
            return events

        if not history:
            dispatcher.utter_message(
                text="Todavía no he generado recomendaciones en esta conversación. Cuando tenga alguna, te las resumiré aquí.",
            )
            return events

        lines = []
        for record in history:
            suggested_dt = _coerce_datetime(record['suggested_time_start'])
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

        dispatcher.utter_message(
            text=f"{header}\n" + "\n".join(lines)
        )
        return events


class ActionCheckFeedbackStatus(Action):
    """Allow users to review their most recent feedback entries."""

    def name(self) -> str:
        return "action_check_feedback_status"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        user_id_raw = tracker.get_slot("user_id")
        role_slot = (tracker.get_slot("user_role") or "player").lower()
        user_role = "admin" if role_slot == "admin" else "player"

        if not user_id_raw:
            dispatcher.utter_message(
                text="No pude validar tu sesión. Inicia sesión otra vez para revisar tus comentarios."
            )
            return []

        try:
            user_id = int(str(user_id_raw).strip())
        except ValueError:
            dispatcher.utter_message(
                text="Necesito que vuelvas a iniciar sesión para reconocer tu cuenta antes de mostrar el feedback."
            )
            return []

        try:
            feedback_entries = await run_in_thread(
                chatbot_service.fetch_feedback_for_user,
                user_id,
                3,
            )
        except DatabaseError:
            dispatcher.utter_message(
                text="No pude acceder al historial de feedback en este momento. Intenta nuevamente más tarde.",
            )
            return []

        if not feedback_entries:
            dispatcher.utter_message(
                text="Aún no registras comentarios sobre tus reservas. Cuando dejes alguno, podré mostrártelo aquí.",
            )
            return []

        lines = []
        for entry in feedback_entries:
            created_dt = _coerce_datetime(entry['created_at'])
            created_at = created_dt.strftime("%d/%m/%Y %H:%M")
            rating_raw = entry.get('rating')
            rating = float(rating_raw) if rating_raw is not None else 0.0
            comment = entry.get('comment') or "(sin comentario)"
            if user_role == "admin":
                lines.append(
                    (
                        f"- Reserva {entry['id_rent']}: calificación {rating:.1f}/5. "
                        f"Comentario: {comment} (enviado el {created_at})."
                    )
                )
            else:
                lines.append(
                    (
                        f"- Partido {entry['id_rent']}: le diste {rating:.1f}/5 y dijiste \"{comment}\" "
                        f"(el {created_at})."
                    )
                )

        if user_role == "admin":
            header = "Aquí tiene los comentarios más recientes que recibimos:"
        else:
            header = "Mira los comentarios que dejaste últimamente:"

        dispatcher.utter_message(
            text=f"{header}\n" + "\n".join(lines)
        )
        return []


class ActionCloseChatSession(Action):
    """Mark the chatbot session as finished in the analytics database."""

    def name(self) -> str:
        return "action_close_chat_session"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        session_id = tracker.get_slot("chatbot_session_id")
        if session_id:
            try:
                await run_in_thread(chatbot_service.close_chat_session, int(session_id))
            except (ValueError, DatabaseError):
                LOGGER.debug("Could not close session %s", session_id)
        return []


class ActionSessionStart(Action):
    """Populate session slots from metadata at the beginning of a conversation."""

    def name(self) -> str:
        return "action_session_start"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        events: List[EventType] = [SessionStarted()]
        metadata = _coerce_metadata(tracker.latest_message.get("metadata"))
        metadata = _enrich_metadata_with_token(metadata)

        LOGGER.info(
            "[ActionSessionStart] conversation=%s metadata=%s slots=%s",
            tracker.sender_id,
            metadata,
            tracker.current_slot_values(),
        )

        user_identifier = metadata.get("user_id") or metadata.get("id_user")
        user_id: Optional[int] = None
        if user_identifier is not None:
            try:
                user_id = int(user_identifier)
            except (TypeError, ValueError):
                events.append(SlotSet("user_id", str(user_identifier)))
                user_id = None
                LOGGER.warning(
                    "[ActionSessionStart] invalid user identifier=%s for conversation=%s",
                    user_identifier,
                    tracker.sender_id,
                )
            else:
                events.append(SlotSet("user_id", str(user_id)))
                LOGGER.info(
                    "[ActionSessionStart] user slot planned with id=%s for conversation=%s",
                    user_id,
                    tracker.sender_id,
                )

        role_value = _normalize_role_from_metadata(metadata)
        user_role_slot_supported = _slot_defined("user_role", domain)
        assigned_role: Optional[str] = None
        if role_value:
            normalized = "admin" if role_value == "admin" else "player"
            if user_role_slot_supported:
                events.append(SlotSet("user_role", normalized))
            else:
                LOGGER.warning(
                    "[ActionSessionStart] domain for conversation=%s does not define slot 'user_role'",
                    tracker.sender_id,
                )
            assigned_role = normalized
            LOGGER.info(
                "[ActionSessionStart] role from metadata=%s normalized=%s",
                role_value,
                normalized,
            )

        if user_role_slot_supported and not _slot_already_planned(events, "user_role"):
            events.append(SlotSet("user_role", "player"))
            if assigned_role is None:
                assigned_role = "player"
        elif not user_role_slot_supported and assigned_role is None:
            assigned_role = "player"

        theme = metadata.get("chat_theme") or metadata.get("theme")
        if not theme:
            theme = tracker.get_slot("chat_theme") or "Reservas y alquileres"

        if assigned_role is None:
            slot_role = tracker.get_slot("user_role")
            assigned_role = slot_role if isinstance(slot_role, str) else None
        if assigned_role is None:
            assigned_role = "player"

        LOGGER.info(
            "[ActionSessionStart] resolved role=%s theme=%s user_id=%s",
            assigned_role,
            theme,
            user_id,
        )

        if user_id is not None:
            try:
                session_id = await run_in_thread(
                    chatbot_service.ensure_chat_session,
                    user_id,
                    theme,
                    assigned_role,
                )
                LOGGER.info(
                    "[ActionSessionStart] ensured session=%s for user_id=%s theme=%s role=%s",
                    session_id,
                    user_id,
                    theme,
                    assigned_role,
                )
            except DatabaseError:
                LOGGER.exception(
                    "[ActionSessionStart] database error ensuring chat session for user_id=%s",
                    user_id,
                )
            else:
                events.append(SlotSet("chat_theme", theme))
                events.append(SlotSet("chatbot_session_id", str(session_id)))

                try:
                    await run_in_thread(
                        chatbot_service.log_chatbot_message,
                        session_id=session_id,
                        intent_id=None,
                        recommendation_id=None,
                        message_text="",
                        bot_response="",
                        response_type="session_started",
                        sender_type="system",
                        user_id=user_id,
                        intent_confidence=None,
                        metadata={**metadata, "theme": theme},
                    )
                    LOGGER.debug(
                        "[ActionSessionStart] logged session_started entry for session=%s",
                        session_id,
                    )
                except DatabaseError:
                    LOGGER.exception(
                        "[ActionSessionStart] database error logging session_started for session=%s",
                        session_id,
                    )

        events.append(ActionExecuted("action_listen"))
        LOGGER.debug(
            "[ActionSessionStart] events planned=%s",
            events,
        )
        return events
