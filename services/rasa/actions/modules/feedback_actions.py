from __future__ import annotations

from typing import List

from rasa_sdk import Action, Tracker
from rasa_sdk.events import EventType, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from ..services.chatbot_service import DatabaseError, chatbot_service
from ..services.chatbot.intent_logging import record_intent_and_log as _record_intent_and_log
from ..domain.chatbot.async_utils import run_in_thread
from ..domain.chatbot.context import (
    coerce_metadata as _coerce_metadata,
    resolve_secured_actor as _resolve_secured_actor,
)
from ..domain.chatbot.time_utils import coerce_datetime as _coerce_datetime


class ActionHandleFeedbackRating(Action):
    """Respond to quick feedback button inputs."""

    def name(self) -> str:
        return "action_handle_feedback_rating"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        latest_metadata = _coerce_metadata(tracker.latest_message.get("metadata"))
        user_id_raw = tracker.get_slot("user_id")
        if not user_id_raw:
            actor = _resolve_secured_actor(
                tracker,
                latest_metadata,
                for_admin_action=False,
            )
            if actor.user_id is not None:
                user_id_raw = str(actor.user_id)

        rating_raw = tracker.get_slot("feedback_rating")
        normalized = str(rating_raw).strip().lower() if rating_raw else ""

        if normalized in {"thumbs_up", "positivo", "positive", "like"}:
            response_text = "¡Gracias por el comentario positivo! Seguiremos mejorando para ti."
            response_type = "feedback_positive"
        elif normalized in {"thumbs_down", "negativo", "negative", "dislike"}:
            response_text = "Gracias por avisarnos. Tu comentario nos ayuda a mejorar."
            response_type = "feedback_negative"
        else:
            response_text = "Gracias por tu tiempo. Si quieres dejar más detalles, cuéntame qué ocurrió en tu reserva."
            response_type = "feedback_unknown"

        dispatcher.utter_message(text=response_text)
        await _record_intent_and_log(
            tracker=tracker,
            session_id=tracker.get_slot("chatbot_session_id"),
            user_id=user_id_raw,
            response_text=response_text,
            response_type=response_type,
        )
        return []


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
        latest_metadata = _coerce_metadata(tracker.latest_message.get("metadata"))
        if not user_id_raw:
            actor = _resolve_secured_actor(
                tracker,
                latest_metadata,
                for_admin_action=False,
            )
            if actor.user_id is not None:
                user_id_raw = str(actor.user_id)
        role_slot = (tracker.get_slot("user_role") or "player").lower()
        user_role = "admin" if role_slot == "admin" else "player"
        session_id = tracker.get_slot("chatbot_session_id")
        theme = tracker.get_slot("chat_theme") or "Reservas y alquileres"

        if not user_id_raw:
            response_text = "No pude validar tu sesión. Inicia sesión otra vez para revisar tus comentarios."
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=None,
                response_text=response_text,
                response_type="feedback_error",
            )
            return []

        try:
            user_id = int(str(user_id_raw).strip())
        except ValueError:
            response_text = (
                "Necesito que vuelvas a iniciar sesión para reconocer tu cuenta antes de mostrar el feedback."
            )
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=None,
                response_text=response_text,
                response_type="feedback_error",
            )
            return []

        events: List[EventType] = []
        if not session_id:
            try:
                new_session_id = await run_in_thread(
                    chatbot_service.ensure_chat_session,
                    user_id,
                    theme,
                    user_role,
                )
                session_id = str(new_session_id)
                events.append(SlotSet("chatbot_session_id", session_id))
            except DatabaseError:
                error_text = (
                    "No logré conectar con tu sesión en este momento. Intenta nuevamente en unos minutos."
                )
                dispatcher.utter_message(text=error_text)
                await _record_intent_and_log(
                    tracker=tracker,
                    session_id=None,
                    user_id=user_id,
                    response_text=error_text,
                    response_type="feedback_error",
                )
                return events

        try:
            feedback_entries = await run_in_thread(
                chatbot_service.fetch_feedback_for_user,
                user_id,
                3,
            )
        except DatabaseError:
            error_text = (
                "No pude acceder al historial de feedback en este momento. Intenta nuevamente más tarde."
            )
            dispatcher.utter_message(text=error_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=user_id,
                response_text=error_text,
                response_type="feedback_error",
            )
            return events

        if not feedback_entries:
            empty_text = (
                "Aún no registras comentarios sobre tus reservas. Cuando dejes alguno, podré mostrártelo aquí."
            )
            dispatcher.utter_message(text=empty_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=user_id,
                response_text=empty_text,
                response_type="feedback_empty",
            )
            return events

        lines = []
        for entry in feedback_entries:
            created_dt = _coerce_datetime(entry["created_at"])
            created_at = created_dt.strftime("%d/%m/%Y %H:%M")
            rating_raw = entry.get("rating")
            rating = float(rating_raw) if rating_raw is not None else 0.0
            comment = entry.get("comment") or "(sin comentario)"
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

        response_text = f"{header}\n" + "\n".join(lines)
        dispatcher.utter_message(text=response_text)
        await _record_intent_and_log(
            tracker=tracker,
            session_id=session_id,
            user_id=user_id,
            response_text=response_text,
            response_type="feedback",
            message_metadata={"feedback_entries": feedback_entries},
        )
        return events


__all__ = [
    "ActionHandleFeedbackRating",
    "ActionCheckFeedbackStatus",
]
