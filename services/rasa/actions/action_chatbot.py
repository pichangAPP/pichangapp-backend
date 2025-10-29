"""Custom actions for booking recommendations and analytics integration."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import Any, Dict, Iterable, List, Optional, Sequence

from dotenv import load_dotenv
from rasa_sdk import Action, Tracker
from rasa_sdk.events import EventType, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from sqlalchemy import Connection, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

load_dotenv()

LOGGER = logging.getLogger(__name__)


@dataclass
class FieldRecommendation:
    """Represents a field recommendation result."""

    id_field: int
    field_name: str
    sport_name: str
    campus_name: str
    district: str
    address: str
    surface: str
    capacity: int
    price_per_hour: float
    open_time: str
    close_time: str


class DatabaseError(RuntimeError):
    """Raised when there is an issue talking to the analytics database."""


class ChatbotDatabase:
    """Helper around SQLAlchemy for chatbot analytics interactions."""

    def __init__(self) -> None:
        self._engine: Optional[Engine] = None
        self._database_url: Optional[str] = None

    def _build_url(self) -> str:
        if self._database_url:
            return self._database_url

        url = os.getenv("CHATBOT_DATABASE_URL") or os.getenv("DATABASE_URL")
        if not url:
            host = os.getenv("POSTGRES_HOST", "localhost")
            port = os.getenv("POSTGRES_PORT", "")
            user = os.getenv("POSTGRES_USER", "")
            password = os.getenv("POSTGRES_PASSWORD", "")
            db_name = os.getenv("POSTGRES_DB", os.getenv("DB_NAME", ""))
            url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"
        self._database_url = url
        return url

    def _get_engine(self) -> Engine:
        if self._engine is None:
            database_url = self._build_url()
            LOGGER.info("Connecting Rasa actions to %s", database_url)
            self._engine = create_engine(
                database_url,
                pool_pre_ping=True,
                pool_size=3,
                max_overflow=2,
                pool_recycle=1800,  # reinicia conexiones cada 30 min
                pool_timeout=30,    # espera hasta 30s si hay timeout
                connect_args={"keepalives": 1, "keepalives_idle": 60, "keepalives_interval": 30, "keepalives_count": 5},
                future=True,
            )

        return self._engine

    @contextmanager
    def connection(self) -> Iterable[Connection]:
        engine = self._get_engine()
        try:
            with engine.begin() as conn:
                yield conn
        except SQLAlchemyError as exc:  # pragma: no cover - defensive
            LOGGER.exception("Database error: %s", exc)
            raise DatabaseError(str(exc)) from exc

    # ------------------------------------------------------------------
    # Chat session helpers
    # ------------------------------------------------------------------
    def ensure_chat_session(self, user_id: int, theme: str) -> int:
        with self.connection() as conn:
            existing = conn.execute(
                text(
                    """
                    SELECT id_chatbot
                    FROM analytics.chatbot
                    WHERE id_user = :user_id
                    ORDER BY started_at DESC
                    LIMIT 1
                    """
                ),
                {"user_id": user_id},
            ).scalar_one_or_none()

            if existing:
                conn.execute(
                    text(
                        """
                        UPDATE analytics.chatbot
                        SET status = 'active'
                        WHERE id_chatbot = :chatbot_id
                        """
                    ),
                    {"chatbot_id": existing},
                )
                return int(existing)

            created = conn.execute(
                text(
                    """
                    INSERT INTO analytics.chatbot (theme, status, id_user, ended_at)
                    VALUES (:theme, 'active', :user_id, now())
                    RETURNING id_chatbot
                    """
                ),
                {"theme": theme, "user_id": user_id},
            ).scalar_one()
            return int(created)

    def close_chat_session(self, chatbot_id: int) -> None:
        with self.connection() as conn:
            conn.execute(
                text(
                    """
                    UPDATE analytics.chatbot
                    SET ended_at = now(), status = 'closed'
                    WHERE id_chatbot = :chatbot_id
                    """
                ),
                {"chatbot_id": chatbot_id},
            )

    # ------------------------------------------------------------------
    # Intents and logging
    # ------------------------------------------------------------------
    def ensure_intent(self, intent_name: str, example_phrases: Sequence[str], response_template: str) -> int:
        with self.connection() as conn:
            payload = {
                "intent_name": intent_name,
                "examples": "\n".join(example_phrases),
                "response_template": response_template,
                "updated_at": datetime.now(),
            }
            existing = conn.execute(
                text("SELECT id_intent FROM analytics.intents WHERE intent_name = :intent_name LIMIT 1"),
                {"intent_name": intent_name}
            ).scalar_one_or_none()

            if existing:
                conn.execute(
                    text("""
                        UPDATE analytics.intents
                        SET example_phrases = :examples,
                            response_template = :response_template,
                            updated_at = :updated_at
                        WHERE id_intent = :id_intent
                    """),
                    {**payload, "id_intent": int(existing)}
                )
                return int(existing)
            else:
                created = conn.execute(
                    text("""
                        INSERT INTO analytics.intents (intent_name, example_phrases, response_template)
                        VALUES (:intent_name, :examples, :response_template)
                        RETURNING id_intent
                    """),
                    payload
                ).scalar_one()
                return int(created)


    def create_recommendation_log(
        self,
        status: str,
        message: str,
        suggested_start: datetime,
        suggested_end: datetime,
        field_id: int,
    ) -> int:
        with self.connection() as conn:
            created = conn.execute(
                text(
                    """
                    INSERT INTO analytics.recomendation_log (
                        status, message, suggested_time_start, suggested_time_end, id_field
                    )
                    VALUES (:status, :message, :start, :end, :field_id)
                    RETURNING id_recommendation_log
                    """
                ),
                {
                    "status": status,
                    "message": message,
                    "start": suggested_start,
                    "end": suggested_end,
                    "field_id": field_id,
                },
            ).scalar_one()
            return int(created)

    def log_chatbot_message(
        self,
        session_id: int,
        intent_id: Optional[int],
        recommendation_id: Optional[int],
        user_message: str,
        bot_response: str,
        response_type: str,
        sender_type: str = "bot",
    ) -> None:
        """Registra cada intercambio entre usuario y bot."""

        with self.connection() as conn:
            conn.execute(
                text("""
                    INSERT INTO analytics.chatbot_log (
                        message,
                        response_type,
                        bot_response,
                        intent_detected,
                        sender_type,
                        id_chatbot,
                        id_intent,
                        id_recommendation_log
                    )
                    VALUES (
                        :message,
                        :response_type,
                        :bot_response,
                        :intent_detected,
                        :sender_type,
                        :id_chatbot,
                        :id_intent,
                        :id_recommendation_log
                    )
                """),
                {
                    "message": user_message,
                    "response_type": response_type,
                    "bot_response": bot_response,
                    "intent_detected": intent_id or None,
                    "sender_type": sender_type,
                    "id_chatbot": session_id,
                    "id_intent": intent_id or None,
                    "id_recommendation_log": recommendation_id or None,
                },
            )


    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------
    def fetch_field_recommendations(
        self,
        sport: Optional[str],
        surface: Optional[str],
        location: Optional[str],
        limit: int = 3,
    ) -> List[FieldRecommendation]:
        with self.connection() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT
                        f.id_field,
                        f.field_name,
                        f.surface,
                        f.capacity,
                        f.price_per_hour,
                        f.open_time,
                        f.close_time,
                        s.sport_name,
                        c.name AS campus_name,
                        c.district,
                        c.address
                    FROM booking.field AS f
                    JOIN booking.sports AS s ON f.id_sport = s.id_sport
                    JOIN booking.campus AS c ON f.id_campus = c.id_campus
                    WHERE (:sport IS NULL OR s.sport_name ILIKE :sport_like)
                      AND (:surface IS NULL OR f.surface ILIKE :surface_like)
                      AND (
                        :location IS NULL
                        OR c.district ILIKE :location_like
                        OR c.address ILIKE :location_like
                        OR c.name ILIKE :location_like
                      )
                    ORDER BY f.price_per_hour ASC, f.capacity DESC
                    LIMIT :limit
                    """
                ),
                {
                    "sport": sport,
                    "surface": surface,
                    "location": location,
                    "sport_like": f"%{sport}%" if sport else None,
                    "surface_like": f"%{surface}%" if surface else None,
                    "location_like": f"%{location}%" if location else None,
                    "limit": limit,
                },
            )

            recommendations: List[FieldRecommendation] = []
            for row in result.mappings():
                recommendations.append(
                    FieldRecommendation(
                        id_field=int(row["id_field"]),
                        field_name=row["field_name"],
                        sport_name=row["sport_name"],
                        campus_name=row["campus_name"],
                        district=row["district"],
                        address=row["address"],
                        surface=row["surface"],
                        capacity=int(row["capacity"]),
                        price_per_hour=float(row["price_per_hour"]),
                        open_time=str(row["open_time"]),
                        close_time=str(row["close_time"]),
                    )
                )
            return recommendations

    def fetch_recommendation_history(self, session_id: int, limit: int = 3) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT
                        r.timestamp,
                        r.status,
                        r.message,
                        r.suggested_time_start,
                        r.suggested_time_end,
                        f.field_name,
                        s.sport_name,
                        c.name AS campus_name
                    FROM analytics.chatbot_log AS cl
                    JOIN analytics.recomendation_log AS r
                        ON cl.id_recommendation_log = r.id_recommendation_log
                    JOIN booking.field AS f ON r.id_field = f.id_field
                    JOIN booking.sports AS s ON f.id_sport = s.id_sport
                    JOIN booking.campus AS c ON f.id_campus = c.id_campus
                    WHERE cl.id_chatbot = :session_id
                    ORDER BY r.timestamp DESC
                    LIMIT :limit
                    """
                ),
                {"session_id": session_id, "limit": limit},
            )
            return [dict(row) for row in result.mappings()]

    def fetch_feedback_for_user(self, user_id: int, limit: int = 3) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT rating, comment, created_at, id_rent
                    FROM analytics.feedback
                    WHERE id_user = :user_id
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                {"user_id": user_id, "limit": limit},
            )
            return [dict(row) for row in result.mappings()]


db_client = ChatbotDatabase()


async def run_in_thread(function: Any, *args: Any, **kwargs: Any) -> Any:
    loop = asyncio.get_running_loop()
    bound = partial(function, *args, **kwargs)
    return await loop.run_in_executor(None, bound)


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
        user_id_raw = tracker.get_slot("user_id")
        theme = tracker.get_slot("chat_theme") or "Reservas y alquileres"

        if not user_id_raw:
            dispatcher.utter_message(
                text="Necesito tu número de usuario para continuar con la recomendación. ¿Podrías indicármelo?",
            )
            return []

        try:
            user_id = int(str(user_id_raw).strip())
        except ValueError:
            dispatcher.utter_message(
                text=(
                    "No pude reconocer ese identificador. Compárteme el ID numérico que usas en la aplicación "
                    "para poder registrar la recomendación."
                )
            )
            return []

        try:
            session_id = await run_in_thread(db_client.ensure_chat_session, user_id, theme)
        except DatabaseError:
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
                db_client.fetch_field_recommendations,
                preferred_sport,
                preferred_surface,
                preferred_location,
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

        summary_lines = []
        for idx, rec in enumerate(recommendations, start=1):
            summary_lines.append(
                (
                    f"{idx}. {rec.field_name} en {rec.campus_name} ({rec.district}). "
                    f"Deporte: {rec.sport_name}. Superficie: {rec.surface}. "
                    f"Capacidad para {rec.capacity} personas. Precio referencial: S/ {rec.price_per_hour:.2f} por hora."
                )
            )

        response_text = (
            "Estas son las canchas que mejor encajan con lo que buscas:\n" + "\n".join(summary_lines)
        )
        dispatcher.utter_message(text=response_text)

        try:
            recommendation_id = await run_in_thread(
                db_client.create_recommendation_log,
                "suggested",
                summary_lines[0],
                start_dt,
                end_dt,
                top_choice.id_field,
            )

            intent_id = await run_in_thread(
                db_client.ensure_intent,
                "request_field_recommendation",
                [
                    "Quiero alquilar una cancha",
                    "¿Qué cancha me recomiendas?",
                    "Necesito reservar una cancha hoy"
                ],
                response_text,
            )

            # registra el intercambio completo
            await run_in_thread(
                db_client.log_chatbot_message,
                session_id,
                intent_id,
                recommendation_id,
                user_message,
                response_text,
                "recommendation",
                sender_type="bot",
            )

        except DatabaseError:
            LOGGER.warning("Could not persist recommendation log for session %s", session_id)

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
        events: List[EventType] = []

        if not session_id and user_id_raw:
            try:
                user_id = int(str(user_id_raw).strip())
                session_id = await run_in_thread(
                    db_client.ensure_chat_session,
                    user_id,
                    tracker.get_slot("chat_theme") or "Reservas y alquileres",
                )
                events.append(SlotSet("chatbot_session_id", str(session_id)))
            except (ValueError, DatabaseError):
                session_id = None

        if not session_id:
            dispatcher.utter_message(
                text=(
                    "Aún no tengo registrada una sesión contigo. Solicita una recomendación "
                    "para que pueda guardar un historial."
                )
            )
            return events

        try:
            history = await run_in_thread(db_client.fetch_recommendation_history, int(session_id))
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

        dispatcher.utter_message(
            text="Este es el resumen de tus últimas recomendaciones:\n" + "\n".join(lines)
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
        if not user_id_raw:
            dispatcher.utter_message(
                text="Para revisar tu feedback necesito tu ID de usuario. ¿Podrías indicármelo?",
            )
            return []

        try:
            user_id = int(str(user_id_raw).strip())
        except ValueError:
            dispatcher.utter_message(
                text="El ID de usuario debe ser numérico. Intenta nuevamente, por favor.",
            )
            return []

        try:
            feedback_entries = await run_in_thread(db_client.fetch_feedback_for_user, user_id)
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
            lines.append(
                (
                    f"- Reserva {entry['id_rent']}: calificación {float(entry['rating']):.1f}/5. "
                    f"Comentario: {entry['comment']} (enviado el {created_at})."
                )
            )

        dispatcher.utter_message(
            text="Estos son tus comentarios más recientes:\n" + "\n".join(lines)
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
                await run_in_thread(db_client.close_chat_session, int(session_id))
            except (ValueError, DatabaseError):
                LOGGER.debug("Could not close session %s", session_id)
        return []
