"""Custom actions for booking recommendations and analytics integration."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone, time as time_of_day
from functools import partial
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import httpx
from sqlalchemy import text
from rasa_sdk import Action, Tracker
from rasa_sdk.events import ActionExecuted, EventType, SessionStarted, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from .infrastructure.config import settings
from .infrastructure.database import get_connection
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
    if isinstance(value, str):
        text = value.strip()
        if text:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                LOGGER.debug("[Metadata] Unable to decode metadata string as JSON")
            else:
                if isinstance(parsed, dict):
                    return dict(parsed)

    return {}

def _coerce_user_identifier(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if stripped.isdigit():
            return int(stripped)
        for separator in (":", "-", "_", "|"):
            candidate = stripped.split(separator)[-1]
            if candidate.isdigit():
                return int(candidate)
        # Fall back to coercing any numeric-like text
        try:
            return int(stripped)
        except ValueError:
            return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

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

    nested_candidates = [metadata.get("customData"), metadata.get("user"), metadata.get("auth")]
    for container in nested_candidates:
        if isinstance(container, dict):
            nested_token = (
                container.get("token")
                or container.get("access_token")
                or container.get("Authorization")
                or container.get("authorization")
            )
            if isinstance(nested_token, str) and nested_token.strip():
                return nested_token

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


def _fetch_managed_campuses(user_id: int) -> List[Dict[str, Any]]:
    query = text(
        """
        SELECT id_campus, name, district, address
        FROM booking.campus
        WHERE id_manager = :user_id
        ORDER BY name
        """
    )
    with get_connection() as connection:
        result = connection.execute(query, {"user_id": user_id})
        campuses: List[Dict[str, Any]] = []
        for row in result:
            mapping = row._mapping
            campuses.append(
                {
                    "id_campus": int(mapping["id_campus"]),
                    "name": mapping.get("name"),
                    "district": mapping.get("district"),
                    "address": mapping.get("address"),
                }
            )
        return campuses


async def _fetch_top_clients_from_analytics(
    campus_id: int,
    *,
    token: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    base_url = settings.ANALYTICS_SERVICE_URL.rstrip("/")
    endpoint = f"{base_url}/analytics/campuses/{campus_id}/top-clients"
    headers: Dict[str, str] = {}
    if token:
        normalized = token.strip()
        if not normalized.lower().startswith("bearer "):
            normalized = f"Bearer {normalized}"
        headers["Authorization"] = normalized
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(endpoint, headers=headers or None)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        LOGGER.warning(
            "[AdminTopClients] analytics returned %s for campus=%s: %s",
            exc.response.status_code,
            campus_id,
            exc,
        )
    except httpx.RequestError as exc:
        LOGGER.warning(
            "[AdminTopClients] request failed for campus=%s: %s",
            campus_id,
            exc,
        )
    except ValueError as exc:
        LOGGER.warning(
            "[AdminTopClients] invalid JSON from analytics for campus=%s: %s",
            campus_id,
            exc,
        )
    return None


def _build_reservation_headers(token: Optional[str]) -> Optional[Dict[str, str]]:
    if not token:
        return None
    normalized = token.strip()
    if not normalized:
        return None
    if not normalized.lower().startswith("bearer "):
        normalized = f"Bearer {normalized}"
    return {"Authorization": normalized}


async def _fetch_user_rent_history(
    user_id: int,
    *,
    token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    base_url = settings.RESERVATION_SERVICE_URL.rstrip("/")
    endpoint = f"{base_url}/rents/users/{user_id}/history"
    headers = _build_reservation_headers(token)
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(endpoint, headers=headers or None)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        LOGGER.warning(
            "[ReservationHistory] status=%s user=%s: %s",
            exc.response.status_code,
            user_id,
            exc,
        )
    except httpx.RequestError as exc:
        LOGGER.warning(
            "[ReservationHistory] request failed for user=%s: %s", user_id, exc
        )
    except ValueError as exc:
        LOGGER.warning(
            "[ReservationHistory] invalid JSON for user=%s: %s", user_id, exc
        )
    return []


async def _fetch_schedule_time_slots(
    field_id: int,
    target_date: date,
    *,
    token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    base_url = settings.RESERVATION_SERVICE_URL.rstrip("/")
    endpoint = f"{base_url}/schedules/time-slots"
    headers = _build_reservation_headers(token)
    params = {"field_id": field_id, "date": target_date.isoformat()}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(endpoint, headers=headers or None, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        LOGGER.warning(
            "[ScheduleSlots] status=%s field=%s date=%s: %s",
            exc.response.status_code,
            field_id,
            target_date,
            exc,
        )
    except httpx.RequestError as exc:
        LOGGER.warning(
            "[ScheduleSlots] request failed for field=%s date=%s: %s",
            field_id,
            target_date,
            exc,
        )
    except ValueError as exc:
        LOGGER.warning(
            "[ScheduleSlots] invalid JSON for field=%s date=%s: %s",
            field_id,
            target_date,
            exc,
        )
    return []


def _parse_datetime_value(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    if " " in normalized and "T" not in normalized:
        normalized = normalized.replace(" ", "T")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _parse_date_value(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if "T" in normalized:
        normalized = normalized.split("T")[0]
    try:
        return date.fromisoformat(normalized)
    except ValueError:
        return None


def _parse_time_value(value: Optional[str]) -> Optional[time_of_day]:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1]
    if " " in normalized and "T" not in normalized:
        normalized = normalized.replace(" ", "T")
    try:
        return time_of_day.fromisoformat(normalized)
    except ValueError:
        try:
            dt = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        return dt.time()


def _ensure_datetime_timezone(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _rent_start_time(rent: Dict[str, Any]) -> Optional[datetime]:
    start = _parse_datetime_value(rent.get("start_time"))
    if start is not None:
        return _ensure_datetime_timezone(start)
    schedule = rent.get("schedule") or {}
    return _ensure_datetime_timezone(_parse_datetime_value(schedule.get("start_time")))


def _rent_end_time(rent: Dict[str, Any]) -> Optional[datetime]:
    end = _parse_datetime_value(rent.get("end_time"))
    if end is not None:
        return _ensure_datetime_timezone(end)
    schedule = rent.get("schedule") or {}
    return _ensure_datetime_timezone(_parse_datetime_value(schedule.get("end_time")))


def _normalize_reservation_status(status: Any) -> str:
    if status is None:
        return ""
    if isinstance(status, str):
        return status.strip().lower()
    return str(status).strip().lower()


def _select_target_rent(
    history: List[Dict[str, Any]],
    requested_date: Optional[date],
    requested_time: Optional[time_of_day],
) -> Tuple[Optional[Dict[str, Any]], str]:
    annotated: List[Tuple[Dict[str, Any], Optional[datetime]]] = []
    for rent in history:
        if _normalize_reservation_status(rent.get("status")) != "reserved":
            continue
        annotated.append((rent, _rent_start_time(rent)))
    if not annotated:
        return None, ""

    def _start_key(item: Tuple[Dict[str, Any], Optional[datetime]]) -> datetime:
        start = item[1]
        return start or datetime.max.replace(tzinfo=timezone.utc)

    def _first(items: List[Tuple[Dict[str, Any], Optional[datetime]]]) -> Dict[str, Any]:
        selected = sorted(items, key=_start_key)[0]
        return selected[0]

    if requested_date and requested_time:
        matches = [
            item
            for item in annotated
            if item[1]
            and item[1].date() == requested_date
            and item[1].time() == requested_time
        ]
        if matches:
            reason = (
                f"Identifiqué la reserva del {requested_date.strftime('%d/%m/%Y')} "
                f"a las {requested_time.strftime('%H:%M')}."
            )
            return _first(matches), reason

    if requested_time:
        matches = [
            item for item in annotated if item[1] and item[1].time() == requested_time
        ]
        if matches:
            reason = (
                f"Identifiqué la reserva que empieza a las {requested_time.strftime('%H:%M')}."
            )
            return _first(matches), reason

    if requested_date:
        matches = [
            item for item in annotated if item[1] and item[1].date() == requested_date
        ]
        if matches:
            reason = f"Filtré por el {requested_date.strftime('%d/%m/%Y')}."
            return _first(matches), reason

    now = datetime.now(timezone.utc)
    future = [item for item in annotated if item[1] and item[1] >= now]
    if future:
        reason = "Tomé la reserva más próxima en la agenda."
        return _first(future), reason

    reason = "Tomé la última reserva registrada."
    last_choice = sorted(annotated, key=_start_key, reverse=True)[0][0]
    return last_choice, reason


def _match_slot_status(
    slots: List[Dict[str, Any]],
    target_start: Optional[datetime],
) -> Optional[str]:
    if not slots or target_start is None:
        return None
    target = _ensure_datetime_timezone(target_start)
    for slot in slots:
        slot_start = _parse_datetime_value(slot.get("start_time"))
        slot_start = _ensure_datetime_timezone(slot_start)
        if slot_start == target:
            status_value = slot.get("status")
            if isinstance(status_value, str):
                return status_value.strip()
            return str(status_value) if status_value is not None else None
    return None


def _describe_slot_availability(status: Optional[str]) -> str:
    if not status:
        return "No pude confirmar la disponibilidad exacta en la agenda de esa cancha."
    normalized = status.strip().lower()
    if normalized in {"available", "libre", "disponible", "open", "free"}:
        return "El horario aparece libre en el calendario, pero el administrador debe confirmarlo."
    if normalized in {"reserved", "ocupado", "booked", "occupied", "taken"}:
        return "En el horario que mencionas la cancha está ocupada según el calendario."
    return (
        f"El calendario reporta el estado \"{status}\" para ese horario, "
        "así que deberías verificarlo con el administrador."
    )


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

def _extract_entity_values(tracker: Tracker, entity_name: str) -> List[str]:
    latest_message = tracker.latest_message or {}
    entities = latest_message.get("entities") or []
    values: List[str] = []
    for entity in entities:
        if entity.get("entity") == entity_name and entity.get("value"):
            text = str(entity["value"]).strip()
            if text:
                values.append(text)
    return values

def _normalize_plain_text(text: Optional[str]) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFD", text)
    normalized = normalized.encode("ascii", "ignore").decode("utf-8")
    return normalized.lower()

_DAY_KEYWORDS: Dict[str, int] = {
    "hoy": 0,
    "esta noche": 0,
    "esta tarde": 0,
    "manana": 1,
    "mañana": 1,
    "pasado manana": 2,
    "fin de semana": 2,
}

_DAYPART_HINTS: Dict[str, str] = {
    "madrugada": "06:00",
    "temprano": "08:00",
    "manana": "09:00",
    "mañana": "09:00",
    "medio dia": "12:00",
    "mediodia": "12:00",
    "tarde": "17:00",
    "noche": "20:00",
}

def _clean_location(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    cleaned = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if cleaned else None

def _infer_date_from_text(text: str) -> Optional[str]:
    normalized = _normalize_plain_text(text)
    if not normalized:
        return None
    base_date = datetime.now(timezone.utc).date()
    for keyword, offset in _DAY_KEYWORDS.items():
        if keyword in normalized:
            return (base_date + timedelta(days=offset)).isoformat()
    return None

def _infer_time_from_text(text: str) -> Optional[str]:
    normalized = _normalize_plain_text(text)
    if not normalized:
        return None
    for keyword, time_hint in _DAYPART_HINTS.items():
        if keyword in normalized:
            return time_hint
    return None

def _guess_preferences_from_context(tracker: Tracker) -> Dict[str, Optional[str]]:
    latest_message = tracker.latest_message or {}
    metadata = _coerce_metadata(latest_message.get("metadata"))
    message_text = latest_message.get("text") or ""

    def _from_metadata(keys: Tuple[str, ...]) -> Optional[str]:
        for key in keys:
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    preferences: Dict[str, Optional[str]] = {}
    provided: Set[str] = set()
    location_values = _extract_entity_values(tracker, "location")
    location_source = None
    location_value = tracker.get_slot("preferred_location")
    if _is_noise_answer(location_value):
        location_value = None
    else:
        location_source = "slot"
    if not location_value and location_values:
        candidate = location_values[0]
        if not _is_noise_answer(candidate):
            location_value = candidate
            location_source = "entity"
    if not location_value:
        meta_location = _from_metadata(("location", "preferred_location", "district"))
        if not _is_noise_answer(meta_location):
            location_value = meta_location
            location_source = "metadata"
    clean_location = _clean_location(location_value) if location_value else None
    if clean_location:
        preferences["preferred_location"] = clean_location
        if location_source in {"entity", "metadata"}:
            provided.add("preferred_location")
    sport_values = _extract_entity_values(tracker, "sport")
    sport_source = None
    sport_value = tracker.get_slot("preferred_sport")
    if _is_noise_answer(sport_value):
        sport_value = None
    else:
        sport_source = "slot"
    if not sport_value and sport_values:
        candidate = sport_values[0]
        if not _is_noise_answer(candidate):
            sport_value = candidate
            sport_source = "entity"
    if not sport_value:
        meta_sport = _from_metadata(("sport", "preferred_sport"))
        if not _is_noise_answer(meta_sport):
            sport_value = meta_sport
            sport_source = "metadata"
    preferences["preferred_sport"] = sport_value
    if sport_value and sport_source in {"entity", "metadata"}:
        provided.add("preferred_sport")

    surface_values = _extract_entity_values(tracker, "surface")
    surface_source = None
    surface_value = tracker.get_slot("preferred_surface")
    if _is_noise_answer(surface_value):
        surface_value = None
    else:
        surface_source = "slot"
    if not surface_value and surface_values:
        candidate = surface_values[0]
        if not _is_noise_answer(candidate):
            surface_value = candidate
            surface_source = "entity"
    if not surface_value:
        meta_surface = _from_metadata(("surface", "preferred_surface"))
        if not _is_noise_answer(meta_surface):
            surface_value = meta_surface
            surface_source = "metadata"
    cleaned_surface = _clean_surface(surface_value) if surface_value else None
    if cleaned_surface:
        preferences["preferred_surface"] = cleaned_surface
        if surface_source in {"entity", "metadata"}:
            provided.add("preferred_surface")
    date_values = _extract_entity_values(tracker, "date")
    date_source = None
    date_value = tracker.get_slot("preferred_date")
    if _is_noise_answer(date_value):
        date_value = None
    else:
        date_source = "slot"
    if not date_value and date_values:
        candidate = date_values[0]
        if not _is_noise_answer(candidate):
            date_value = candidate
            date_source = "entity"
    if not date_value:
        meta_date = _from_metadata(("preferred_date", "date"))
        if not _is_noise_answer(meta_date):
            date_value = meta_date
            date_source = "metadata"
    inferred_date = date_value or _infer_date_from_text(message_text)
    if inferred_date:
        preferences["preferred_date"] = inferred_date
        if date_source in {"entity", "metadata"}:
            provided.add("preferred_date")
    time_values = _extract_entity_values(tracker, "time")
    time_source = None
    time_value = tracker.get_slot("preferred_start_time")
    if _is_noise_answer(time_value):
        time_value = None
    else:
        time_source = "slot"
    if not time_value and time_values:
        candidate = time_values[0]
        if not _is_noise_answer(candidate):
            time_value = candidate
            time_source = "entity"
    if not time_value:
        meta_time = _from_metadata(("preferred_start_time", "time"))
        if not _is_noise_answer(meta_time):
            time_value = meta_time
            time_source = "metadata"
    inferred_time = time_value or _infer_time_from_text(message_text)
    if inferred_time:
        preferences["preferred_start_time"] = inferred_time
        if time_source in {"entity", "metadata"}:
            provided.add("preferred_start_time")
    end_time_slot = tracker.get_slot("preferred_end_time")
    end_time_meta = _from_metadata(("preferred_end_time",))
    preferences["preferred_end_time"] = end_time_slot or end_time_meta
    if (
        not preferences.get("preferred_end_time")
        and preferences.get("preferred_start_time")
    ):
        components = _extract_time_components(preferences["preferred_start_time"])
        if components:
            hour, minute = components
            end_dt = datetime.now(timezone.utc).replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            ) + timedelta(hours=1)
            preferences["preferred_end_time"] = end_dt.strftime("%H:%M")

    preferences["preferred_budget"] = (
        tracker.get_slot("preferred_budget") or _from_metadata(("preferred_budget", "budget"))
    )
    if preferences.get("preferred_budget") and _from_metadata(("preferred_budget", "budget")):
        provided.add("preferred_budget")
    preferences["_provided"] = provided
    return preferences

def _build_preference_summary(preferences: Dict[str, Optional[str]]) -> Optional[str]:
    fragments: List[str] = []
    provided: Set[str] = preferences.get("_provided", set())  # type: ignore[arg-type]
    location = preferences.get("preferred_location")
    date_value = _format_short_date(preferences.get("preferred_date")) if "preferred_date" in provided else None
    start_time = _format_short_time(preferences.get("preferred_start_time")) if "preferred_start_time" in provided else None
    surface = _clean_surface(preferences.get("preferred_surface")) if "preferred_surface" in provided else None
    sport = preferences.get("preferred_sport") if "preferred_sport" in provided else None

    if location:
        fragments.append(f"en {location}")
    if date_value:
        fragments.append(f"para {date_value}")
    if start_time:
        fragments.append(f"cerca de las {start_time}")
    if surface:
        fragments.append(f"en superficie {surface}")
    if sport:
        fragments.append(f"para {sport}")

    if not fragments:
        return None

    message = "Perfecto, reviso opciones " + ", ".join(fragments) + "."
    missing_slots = [
        label
        for key, label in [
            ("preferred_date", "la fecha"),
            ("preferred_start_time", "el horario"),
            ("preferred_surface", "la superficie"),
            ("preferred_sport", "el deporte"),
        ]
        if not preferences.get(key)
    ]
    if missing_slots:
        message += " Si tienes detalles extra sobre " + " o ".join(missing_slots) + ", cuéntamelo."
    return message

def _format_short_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.strftime("%d/%m")
    except ValueError:
        digits = re.sub(r"\D", "", value)
        if len(digits) in {6, 8}:
            return f"{digits[-2:]}/{digits[-4:-2]}"
        return None

def _format_short_time(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    components = _extract_time_components(value)
    if components is None:
        return None
    hour, minute = components
    return f"{hour:02d}:{minute:02d}"

def _clean_surface(surface: Optional[str]) -> Optional[str]:
    if not surface:
        return None
    normalized = surface.strip().lower()
    allowed_keywords = {
        "grass",
        "grass natural",
        "natural",
        "sintetico",
        "sintético",
        "sintético premium",
        "artificial",
        "losa",
        "pasto",
        "pasto natural",
        "pasto sintetico",
        "pasto sintético",
    }
    if normalized in allowed_keywords:
        return surface.strip()
    if any(keyword in normalized for keyword in ("grass", "synthetic", "sintet", "artificial", "losa", "pasto")):
        return surface.strip()
    return None

def _apply_default_preferences(preferences: Dict[str, Optional[str]], metadata: Dict[str, Any]) -> Dict[str, Optional[str]]:
    now = datetime.now(timezone.utc)
    if not preferences.get("preferred_date"):
        preferences["preferred_date"] = now.date().isoformat()
    if not preferences.get("preferred_start_time"):
        rounded = now + timedelta(minutes=30)
        preferences["preferred_start_time"] = rounded.strftime("%H:%M")
    if not preferences.get("preferred_end_time") and preferences.get("preferred_start_time"):
        components = _extract_time_components(preferences["preferred_start_time"])
        if components:
            hour, minute = components
            end_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(hours=1)
            preferences["preferred_end_time"] = end_dt.strftime("%H:%M")
    if not preferences.get("preferred_location"):
        default_location = metadata.get("district") or metadata.get("location") or metadata.get("preferred_location")
        if isinstance(default_location, str) and default_location.strip():
            preferences["preferred_location"] = default_location.strip()
    return preferences

_NOISE_KEYWORDS = {
    "ninguno",
    "ninguna",
    "ningun",
    "nadie",
    "cualquiera",
    "lo que sea",
    "como quieras",
    "no importa",
    "da igual",
    "me da igual",
    "no se",
    "nose",
    "adios",
    "adiós",
    "bye",
    "salir",
    "cancelar",
    "ningún dato",
    "ya fue",
    "olvida",
    "olvidalo",
}

def _is_noise_answer(value: Optional[str]) -> bool:
    if value is None:
        return True
    normalized = _normalize_plain_text(value)
    if not normalized:
        return True
    normalized = normalized.strip()
    if not normalized:
        return True
    if normalized in _NOISE_KEYWORDS:
        return True
    return False

_TIME_FORMATS: Tuple[str, ...] = (
    "%H:%M",
    "%H.%M",
    "%Hh%M",
    "%H%M",
    "%H",
    "%I:%M%p",
    "%I.%M%p",
    "%Ih%M%p",
    "%I%p",
    "%I %p",
)

_DATE_FORMATS: Tuple[str, ...] = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%d-%m-%Y",
    "%d.%m.%Y",
)

_PRICE_CONTEXT_KEYWORDS = (
    "s/",
    "s/.",
    "soles",
    "presup",
    "precio",
    "cost",
    "econ",
    "barat",
    "lucas",
    "budget",
)

_PRICE_PRIORITY_KEYWORDS = ("econom", "econó", "barat", "ahorro")

_BUDGET_RANGE_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"entre\s*(\d+(?:[.,]\d+)?)\s*(?:y|e|a|-)\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE),
    re.compile(r"(?:de|desde)\s*(\d+(?:[.,]\d+)?)\s*(?:a|-)\s*(\d+(?:[.,]\d+)?)\s*(?:soles?|s\/\.?|s\/|\$)?", re.IGNORECASE),
    re.compile(r"(?:s\/\.?|s\/|\$)\s*(\d+(?:[.,]\d+)?)\s*-\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE),
)
_BUDGET_MAX_PATTERN = re.compile(
    r"(?:hasta|máximo|maximo|tope|menos de|menor a|presupuesto(?:\s+de)?|budget(?:\s+de)?|precio(?:\s+tope)?)\s*(\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)
_BUDGET_MIN_PATTERN = re.compile(
    r"(?:desde|mínimo|minimo|más de|mas de|mayor a|superior a)\s*(\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)
_BUDGET_GENERIC_PATTERN = re.compile(r"(?:s\/\.?|s\/|\$)\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)
_BUDGET_SOL_PATTERN = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:soles|lucas)", re.IGNORECASE)


def _extract_time_components(time_value: Optional[str]) -> Optional[Tuple[int, int]]:
    if not time_value:
        return None
    raw = str(time_value).strip()
    if not raw:
        return None
    normalized = raw.lower()
    replacements = {
        "a. m.": "am",
        "p. m.": "pm",
        "a.m.": "am",
        "p.m.": "pm",
        " hrs": "h",
        " hr": "h",
        " horas": "h",
        " hora": "h",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    normalized = normalized.replace("hs", "h")
    variants = {
        normalized,
        normalized.replace(".", ":"),
        normalized.replace(" ", ""),
        normalized.replace(".", "").replace(" ", ""),
    }
    digits_only = re.sub(r"[^\d]", "", normalized)
    if len(digits_only) >= 3 and len(digits_only) <= 4:
        variants.add(f"{digits_only[:-2]}:{digits_only[-2:]}")
    elif digits_only:
        variants.add(digits_only)

    for candidate in variants:
        for fmt in _TIME_FORMATS:
            try:
                parsed = datetime.strptime(candidate, fmt)
            except ValueError:
                continue
            return parsed.hour, parsed.minute
    LOGGER.debug("[TimeParser] Unable to parse time_value=%s", time_value)
    return None


def _coerce_time_value(time_value: Optional[str]) -> Optional[time_of_day]:
    components = _extract_time_components(time_value)
    if not components:
        return None
    hour, minute = components
    try:
        return time_of_day(hour=hour, minute=minute)
    except ValueError:
        return None


def _mentions_price_context(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in _PRICE_CONTEXT_KEYWORDS)


def _detect_price_focus(text: Optional[str]) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(keyword in lowered for keyword in _PRICE_PRIORITY_KEYWORDS)


_RATING_PRIORITY_KEYWORDS = (
    "mejor valorad",
    "mejores valorad",
    "mejor calificada",
    "mejores calificadas",
    "mejor puntuada",
    "mejores puntuadas",
    "mejor reseña",
    "mejores reseñas",
    "rating",
    "puntaje",
    "top",
)


def _detect_rating_focus(text: Optional[str]) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(keyword in lowered for keyword in _RATING_PRIORITY_KEYWORDS)


def _budget_string_to_float(value: str) -> Optional[float]:
    normalized = value.replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


def _parse_budget_from_text(text: Optional[str], *, force: bool = False) -> Tuple[Optional[float], Optional[float]]:
    if not text:
        return (None, None)
    candidate = str(text).strip()
    if not candidate:
        return (None, None)
    lowered = candidate.lower()
    if not force and not _mentions_price_context(lowered):
        return (None, None)

    for pattern in _BUDGET_RANGE_PATTERNS:
        match = pattern.search(candidate)
        if match:
            low = _budget_string_to_float(match.group(1))
            high = _budget_string_to_float(match.group(2))
            if low is None or high is None:
                continue
            return (min(low, high), max(low, high))

    match = _BUDGET_MAX_PATTERN.search(candidate)
    if match:
        value = _budget_string_to_float(match.group(1))
        return (None, value)

    match = _BUDGET_MIN_PATTERN.search(candidate)
    if match:
        value = _budget_string_to_float(match.group(1))
        return (value, None)

    match = _BUDGET_GENERIC_PATTERN.search(candidate)
    if match:
        value = _budget_string_to_float(match.group(1))
        return (None, value)

    match = _BUDGET_SOL_PATTERN.search(candidate)
    if match:
        value = _budget_string_to_float(match.group(1))
        return (None, value)

    return (None, None)


def _format_budget_range(min_price: Optional[float], max_price: Optional[float]) -> Optional[str]:
    if min_price is not None and max_price is not None:
        return f"con presupuesto entre S/ {min_price:.2f} y S/ {max_price:.2f}"
    if max_price is not None:
        return f"con presupuesto hasta S/ {max_price:.2f}"
    if min_price is not None:
        return f"con presupuesto desde S/ {min_price:.2f}"
    return None


def _extract_budget_preferences(tracker: Tracker) -> Tuple[Optional[float], Optional[float], bool]:
    latest_message = tracker.latest_message or {}
    metadata = _coerce_metadata(latest_message.get("metadata"))
    message_text = latest_message.get("text") or ""
    price_focus = _detect_price_focus(message_text)

    candidate_texts: List[Tuple[str, bool]] = []
    slot_budget = tracker.get_slot("preferred_budget")
    if slot_budget:
        candidate_texts.append((str(slot_budget), True))

    metadata_budget = metadata.get("budget") or metadata.get("preferred_budget")
    if metadata_budget:
        candidate_texts.append((str(metadata_budget), True))

    entities = latest_message.get("entities") or []
    for entity in entities:
        if entity.get("entity") == "budget" and entity.get("value"):
            candidate_texts.append((str(entity["value"]), True))

    if message_text and (_mentions_price_context(message_text) or price_focus):
        candidate_texts.append((message_text, False))

    min_price: Optional[float] = None
    max_price: Optional[float] = None
    for text_value, force in candidate_texts:
        low, high = _parse_budget_from_text(text_value, force=force)
        if low is not None:
            min_price = low if min_price is None else max(min_price, low)
        if high is not None:
            max_price = high if max_price is None else min(max_price, high)

    return min_price, max_price, price_focus


def _time_to_string(value: Optional[time_of_day]) -> Optional[str]:
    return value.strftime("%H:%M") if value else None


def _serialize_filter_payload(
    *,
    sport: Optional[str],
    surface: Optional[str],
    location: Optional[str],
    min_price: Optional[float],
    max_price: Optional[float],
    target_time: Optional[time_of_day],
    prioritize_price: bool,
    prioritize_rating: bool,
) -> Dict[str, Any]:
    return {
        "sport": sport,
        "surface": surface,
        "location": location,
        "min_price": min_price,
        "max_price": max_price,
        "target_time": _time_to_string(target_time),
        "price_priority": prioritize_price,
        "rating_priority": prioritize_rating,
    }


def _describe_relaxations(
    drops: Set[str],
    *,
    sport: Optional[str],
    surface: Optional[str],
    location: Optional[str],
    min_price: Optional[float],
    max_price: Optional[float],
    target_time: Optional[time_of_day],
) -> List[str]:
    notes: List[str] = []
    if "budget" in drops and (min_price is not None or max_price is not None):
        notes.append("No había canchas exactas en ese presupuesto, así que amplié un poco el rango.")
    if "time" in drops and target_time is not None:
        notes.append("No vi disponibilidad en ese horario puntual; te muestro opciones cercanas.")
    if "location" in drops and location:
        notes.append(f"Amplié la búsqueda fuera de {location} para darte alternativas.")
    if "surface" in drops and surface:
        notes.append("Incluí otras superficies similares para que no te quedes sin cancha.")
    if "sport" in drops and sport:
        notes.append(f"No encontré {sport} disponible, así que sumé canchas populares que podrías adaptar.")
    return notes


async def _fetch_recommendations_with_relaxation(
    *,
    sport: Optional[str],
    surface: Optional[str],
    location: Optional[str],
    min_price: Optional[float],
    max_price: Optional[float],
    target_time: Optional[time_of_day],
    prioritize_price: bool,
    prioritize_rating: bool,
    limit: int,
) -> Tuple[List[FieldRecommendation], Dict[str, Any], List[str], str]:
    requests = [
        ("exact_match", set()),
        ("relaxed_budget", {"budget"}),
        ("relaxed_time", {"budget", "time"}),
        ("relaxed_surface", {"budget", "time", "surface"}),
        ("location_focus", {"budget", "time", "surface", "sport"}),
        ("relaxed_location", {"budget", "time", "surface", "sport", "location"}),
        ("generic_popular", {"budget", "time", "surface", "sport", "location", "price_priority"}),
    ]
    for label, drops in requests:
        params_sport = None if "sport" in drops else sport
        params_surface = None if "surface" in drops else surface
        params_location = None if "location" in drops else location
        params_min_price = None if "budget" in drops else min_price
        params_max_price = None if "budget" in drops else max_price
        params_time = None if "time" in drops else target_time
        # Keep prioritizing price even if ranges were expanded so the user still gets opciones económicas.
        params_prioritize_price = False if "price_priority" in drops else prioritize_price
        params_prioritize_rating = prioritize_rating
        recommendations: List[FieldRecommendation] = await run_in_thread(
            chatbot_service.fetch_field_recommendations,
            sport=params_sport,
            surface=params_surface,
            location=params_location,
            limit=limit,
            min_price=params_min_price,
            max_price=params_max_price,
            target_time=params_time,
            prioritize_price=params_prioritize_price,
            prioritize_rating=params_prioritize_rating,
        )
        if recommendations:
            applied_filters = _serialize_filter_payload(
                sport=params_sport,
                surface=params_surface,
                location=params_location,
                min_price=params_min_price,
                max_price=params_max_price,
                target_time=params_time,
                prioritize_price=params_prioritize_price,
                prioritize_rating=params_prioritize_rating,
            )
            notes = _describe_relaxations(
                drops,
                sport=sport,
                surface=surface,
                location=location,
                min_price=min_price,
                max_price=max_price,
                target_time=target_time,
            )
            return recommendations, applied_filters, notes, label

    fallback_filters = _serialize_filter_payload(
        sport=sport,
        surface=surface,
        location=location,
        min_price=min_price,
        max_price=max_price,
        target_time=target_time,
        prioritize_price=prioritize_price,
        prioritize_rating=prioritize_rating,
    )
    return [], fallback_filters, [], "no_results"


async def _persist_recommendation_logs(
    *,
    user_id: int,
    recommendations: List[FieldRecommendation],
    summaries: List[str],
    start_dt: datetime,
    end_dt: datetime,
) -> Tuple[Optional[int], List[int]]:
    stored_ids: List[int] = []
    primary_id: Optional[int] = None
    for idx, (rec, message_text) in enumerate(zip(recommendations, summaries)):
        status = "suggested" if idx == 0 else "suggested_alternative"
        try:
            rec_id = await run_in_thread(
                chatbot_service.create_recommendation_log,
                status=status,
                message=message_text,
                suggested_start=start_dt,
                suggested_end=end_dt,
                field_id=rec.id_field,
                user_id=user_id,
            )
        except DatabaseError:
            LOGGER.exception(
                "[ActionSubmitFieldRecommendationForm] database error creating recommendation log for field_id=%s",
                rec.id_field,
            )
            continue
        stored_ids.append(rec_id)
        if idx == 0:
            primary_id = rec_id
    return primary_id, stored_ids


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
    base = datetime.now(timezone.utc)
    if date_value:
        raw = str(date_value).strip()
        if raw:
            lowered = raw.lower()
            if lowered in {"hoy", "today"}:
                date_part = base
            elif lowered in {"mañana", "manana"}:
                date_part = base + timedelta(days=1)
            elif lowered in {"pasado mañana", "pasado manana"}:
                date_part = base + timedelta(days=2)
            else:
                parsed: Optional[datetime] = None
                try:
                    parsed = datetime.fromisoformat(raw)
                except ValueError:
                    for fmt in _DATE_FORMATS:
                        try:
                            parsed = datetime.strptime(raw, fmt)
                        except ValueError:
                            continue
                        else:
                            break
                if parsed is None:
                    LOGGER.debug("[TimeParser] Using current date because date_value=%s is invalid", date_value)
                    parsed = base
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                date_part = parsed
        else:
            date_part = base
    else:
        date_part = base

    if date_part.tzinfo is None:
        date_part = date_part.replace(tzinfo=timezone.utc)

    if time_value:
        time_components = _extract_time_components(time_value)
        if time_components is None:
            LOGGER.debug("[TimeParser] Falling back to existing hour for time_value=%s", time_value)
            return date_part
        hour, minute = time_components
        date_part = date_part.replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )
    return date_part

async def _record_intent_and_log(
    *,
    tracker: Tracker,
    session_id: Optional[int | str],
    user_id: Optional[int | str],
    response_text: str,
    response_type: str,
    recommendation_id: Optional[int] = None,
    message_metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Persist intent statistics and log the combined user/bot message."""

    latest_message = tracker.latest_message or {}
    user_message = latest_message.get("text") or ""
    base_metadata = _coerce_metadata(latest_message.get("metadata"))
    metadata: Dict[str, Any] = dict(base_metadata)
    if message_metadata:
        metadata.update(message_metadata)

    intent_data = latest_message.get("intent") or {}
    intent_name = intent_data.get("name") or "nlu_fallback"
    confidence = intent_data.get("confidence")
    detected = bool(intent_name) and intent_name != "nlu_fallback"
    false_positive = not detected

    example_phrases = [user_message] if user_message else []
    if not example_phrases:
        example_phrases.append(intent_name)

    intent_id: Optional[int] = None
    try:
        intent_id = await run_in_thread(
            chatbot_service.ensure_intent,
            intent_name=intent_name,
            example_phrases=example_phrases,
            response_template=response_text,
            confidence=confidence,
            detected=detected,
            false_positive=false_positive,
            source_model=metadata.get("model") or metadata.get("pipeline"),
        )
    except DatabaseError:
        LOGGER.exception(
            "[Analytics] Unable to persist intent=%s for conversation=%s",
            intent_name,
            tracker.sender_id,
        )

    session_value = _coerce_user_identifier(session_id) if session_id is not None else None
    user_value = _coerce_user_identifier(user_id) if user_id is not None else None

    slot_session = tracker.get_slot("chatbot_session_id")
    if session_value is None and slot_session:
        session_value = _coerce_user_identifier(slot_session)

    slot_user = tracker.get_slot("user_id")
    if user_value is None and slot_user:
        user_value = _coerce_user_identifier(slot_user)

    if user_value is None:
        metadata_user = metadata.get("user_id") or metadata.get("id_user")
        user_value = _coerce_user_identifier(metadata_user)

    if session_value is None:
        metadata_session = metadata.get("chatbot_session_id")
        session_value = _coerce_user_identifier(metadata_session)

    if session_value is None and user_value is not None:
        theme = tracker.get_slot("chat_theme") or metadata.get("chat_theme") or "Reservas y alquileres"
        role_source = tracker.get_slot("user_role") or metadata.get("user_role") or metadata.get("role")
        role_name = "admin" if isinstance(role_source, str) and role_source.lower() == "admin" else "player"
        try:
            session_value = await run_in_thread(
                chatbot_service.ensure_chat_session,
                int(user_value),
                theme,
                role_name,
            )
            LOGGER.info(
                "[Analytics] ensured session_id=%s on the fly for sender=%s",
                session_value,
                tracker.sender_id,
            )
        except DatabaseError:
            LOGGER.exception(
                "[Analytics] unable to ensure session for user_id=%s while logging",
                user_value,
            )

    if session_value is None:
        LOGGER.debug(
            "[Analytics] Skipping chatbot log because session_id is missing for sender=%s",
            tracker.sender_id,
        )
        return

    metadata.setdefault("slots_snapshot", tracker.current_slot_values())
    if user_value is not None:
        metadata.setdefault("user_id", int(user_value))
        metadata.setdefault("id_user", int(user_value))
    metadata.setdefault("chatbot_session_id", session_value)

    try:
        await run_in_thread(
            chatbot_service.log_chatbot_message,
            session_id=session_value,
            intent_id=intent_id,
            recommendation_id=recommendation_id,
            message_text=user_message,
            bot_response=response_text,
            response_type=response_type,
            sender_type="bot",
            user_id=user_value,
            intent_confidence=confidence,
            metadata=metadata,
        )
    except DatabaseError:
        LOGGER.exception(
            "[Analytics] Failed to log chatbot message for session_id=%s",
            session_value,
        )

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

        requested_filters = _serialize_filter_payload(
            sport=preferred_sport,
            surface=preferred_surface,
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
            ) = await _fetch_recommendations_with_relaxation(
                sport=preferred_sport,
                surface=preferred_surface,
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
        if location_used:
            filter_fragments.append(f"en {location_used}")
        target_time_str = applied_filters.get("target_time")
        if target_time_str:
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

        response_text = (
            f"{intro}{filters_sentence}{notes_sentence}{inference_sentence}\n"
            + "\n".join(summary_lines)
            + f"\n{closing}"
        )
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

        if campus_context is None:
            try:
                campuses = await run_in_thread(_fetch_managed_campuses, user_id)
            except DatabaseError:
                LOGGER.exception(
                    "[ActionProvideAdminCampusTopClients] database error fetching campuses for user_id=%s",
                    user_id,
                )
            else:
                if campuses:
                    campus_context = campuses[0]
                    events.append(SlotSet("managed_campus_id", str(campus_context["id_campus"])))
                    campus_name = campus_context.get("name")
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

        campus_display = campus_context.get("name") or "tu campus"
        auth_token = _extract_token_from_metadata(metadata)
        top_clients_data = await _fetch_top_clients_from_analytics(
            campus_context["id_campus"],
            token=auth_token,
        )
        if top_clients_data is None:
            response_text = (
                "No pude consultar los clientes frecuentes en este momento. "
                "Por favor intenta nuevamente en unos minutos."
            )
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=user_id,
                response_text=response_text,
                response_type="admin_top_clients_unavailable",
                message_metadata={"campus_id": campus_context["id_campus"]},
            )
            return events

        frequent_clients: List[Dict[str, Any]] = top_clients_data.get("frequent_clients") or []
        if not frequent_clients:
            response_text = (
                f"Por ahora no hay clientes frecuentes registrados para {campus_display}."
            )
            dispatcher.utter_message(text=response_text)
            await _record_intent_and_log(
                tracker=tracker,
                session_id=session_id,
                user_id=user_id,
                response_text=response_text,
                response_type="admin_top_clients_empty",
                message_metadata={"campus_id": campus_context["id_campus"], "campus_name": campus_display},
            )
            return events

        lines: List[str] = []
        for index, client in enumerate(frequent_clients, start=1):
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

        response_text = (
            f"Estimado administrador, estos son los jugadores que más rentan en {campus_display}:\n"
            + "\n".join(lines)
        )
        response_metadata = {
            "analytics": {
                "response_type": "admin_top_clients",
                "campus_id": campus_context["id_campus"],
                "campus_name": campus_display,
                "client_count": len(frequent_clients),
                "source": "analytics_service",
            },
            "top_clients": frequent_clients,
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
            user_id=tracker.get_slot("user_id"),
            response_text=response_text,
            response_type=response_type,
        )
        return []


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

        history = await _fetch_user_rent_history(user_id, token=user_token)
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


class ActionEnsureUserRole(Action):
    def name(self) -> str:
        return "action_ensure_user_role"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[EventType]:
        metadata = _coerce_metadata(tracker.latest_message.get("metadata"))
        normalized_role = _normalize_role_from_metadata(metadata)
        if normalized_role is None:
            normalized_role = tracker.get_slot("user_role") or "player"
        events: List[EventType] = []
        if tracker.get_slot("user_role") != normalized_role:
            events.append(SlotSet("user_role", normalized_role))
        return events


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
        user_id = tracker.get_slot("user_id")
        response_text = "Sesión cerrada"
        if session_id:
            try:
                await run_in_thread(chatbot_service.close_chat_session, int(session_id))
            except (ValueError, DatabaseError):
                LOGGER.debug("Could not close session %s", session_id)
        await _record_intent_and_log(
            tracker=tracker,
            session_id=session_id,
            user_id=user_id,
            response_text=response_text,
            response_type="session_closed",
        )
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
        if user_identifier is None:
            nested_user = metadata.get("user")
            if isinstance(nested_user, dict):
                user_identifier = nested_user.get("id") or nested_user.get("id_user")

        user_id: Optional[int] = None
        if user_identifier is not None:
            user_id = _coerce_user_identifier(user_identifier)
            if user_id is None:
                events.append(SlotSet("user_id", str(user_identifier)))
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

        if user_id is None:
            sender_fallback = _coerce_user_identifier(tracker.sender_id)
            if sender_fallback is not None and not _slot_already_planned(events, "user_id"):
                user_id = sender_fallback
                events.append(SlotSet("user_id", str(user_id)))
                LOGGER.info(
                    "[ActionSessionStart] derived user id=%s from sender_id=%s for conversation=%s",
                    user_id,
                    tracker.sender_id,
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

        campus_info: Optional[Dict[str, Any]] = None
        if assigned_role == "admin" and user_id is not None:
            try:
                campuses = await run_in_thread(_fetch_managed_campuses, user_id)
            except DatabaseError:
                LOGGER.exception(
                    "[ActionSessionStart] database error fetching campuses for user_id=%s",
                    user_id,
                )
            else:
                if campuses:
                    campus_info = campuses[0]
                    events.append(SlotSet("managed_campus_id", str(campus_info["id_campus"])))
                    campus_name = campus_info.get("name")
                    if campus_name:
                        events.append(SlotSet("managed_campus_name", campus_name))

        LOGGER.info(
            "[ActionSessionStart] resolved role=%s theme=%s user_id=%s",
            assigned_role,
            theme,
            user_id,
        )

        if user_id is not None:
            metadata.setdefault("id_user", user_id)
            metadata.setdefault("user_id", user_id)
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

                initial_user_text = tracker.latest_message.get("text") or ""

                try:
                    await run_in_thread(
                        chatbot_service.log_chatbot_message,
                        session_id=session_id,
                        intent_id=None,
                        recommendation_id=None,
                        message_text=initial_user_text,
                        bot_response="session_started",
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
