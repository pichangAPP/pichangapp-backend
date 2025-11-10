"""Custom actions for booking recommendations and analytics integration."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, timezone, time as time_of_day
from functools import partial
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

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
) -> Dict[str, Any]:
    return {
        "sport": sport,
        "surface": surface,
        "location": location,
        "min_price": min_price,
        "max_price": max_price,
        "target_time": _time_to_string(target_time),
        "price_priority": prioritize_price,
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
    limit: int,
) -> Tuple[List[FieldRecommendation], Dict[str, Any], List[str], str]:
    requests = [
        ("exact_match", set()),
        ("relaxed_budget", {"budget"}),
        ("relaxed_time", {"budget", "time"}),
        ("relaxed_location", {"budget", "time", "location"}),
        ("relaxed_surface", {"budget", "time", "location", "surface"}),
        ("generic_popular", {"budget", "time", "location", "surface", "sport"}),
    ]
    for label, drops in requests:
        params_sport = None if "sport" in drops else sport
        params_surface = None if "surface" in drops else surface
        params_location = None if "location" in drops else location
        params_min_price = None if "budget" in drops else min_price
        params_max_price = None if "budget" in drops else max_price
        params_time = None if "time" in drops else target_time
        # Keep prioritizing price even if ranges were expanded so the user still gets opciones económicas.
        params_prioritize_price = prioritize_price
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

        preferred_sport = tracker.get_slot("preferred_sport")
        preferred_surface = tracker.get_slot("preferred_surface")
        preferred_location = tracker.get_slot("preferred_location")
        preferred_date = tracker.get_slot("preferred_date")
        preferred_start_time = tracker.get_slot("preferred_start_time")
        preferred_end_time = tracker.get_slot("preferred_end_time")
        min_budget, max_budget, price_focus = _extract_budget_preferences(tracker)
        target_time = _coerce_time_value(preferred_start_time)
        prioritize_price = price_focus or min_budget is not None or max_budget is not None

        requested_filters = _serialize_filter_payload(
            sport=preferred_sport,
            surface=preferred_surface,
            location=preferred_location,
            min_price=min_budget,
            max_price=max_budget,
            target_time=target_time,
            prioritize_price=prioritize_price,
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
        filters_sentence = ""
        if filter_fragments:
            filters_sentence = " Consideré " + ", ".join(filter_fragments) + "."
        notes_sentence = ""
        if relaxation_notes:
            notes_sentence = " " + " ".join(relaxation_notes)

        response_text = f"{intro}{filters_sentence}{notes_sentence}\n" + "\n".join(summary_lines) + f"\n{closing}"
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

        analytics_payload: Dict[str, Any] = {
            "response_type": "recommendation",
            "suggested_start": start_dt.isoformat(),
            "suggested_end": end_dt.isoformat(),
            "recommended_field_id": top_choice.id_field,
            "candidate_recommendations": [rec.field_name for rec in recommendations],
            "filters": {
                "requested": requested_filters,
                "applied": applied_filters,
            },
            "filter_summary": filter_fragments,
            "relaxation_notes": relaxation_notes,
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

        response_metadata = {"analytics": analytics_payload}
        dispatcher.utter_message(text=response_text, metadata=response_metadata)
        await _record_intent_and_log(
            tracker=tracker,
            session_id=session_id,
            user_id=user_id,
            response_text=response_text,
            response_type="recommendation",
            recommendation_id=recommendation_id,
            message_metadata=response_metadata,
        )

        events: List[EventType] = [
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
        if price_focus or min_budget is not None or max_budget is not None:
            tips.append(
                "Configura promociones escalonadas (2x1, créditos de lealtad) para los presupuestos que los jugadores mencionan con más frecuencia."
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

        response_text = "Estas son algunas recomendaciones para optimizar la operación de tus sedes:\n"
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
        response_metadata = {"analytics": analytics_payload}
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
        response_text = "Iniciando formulario de recomendación."
        await _record_intent_and_log(
            tracker=tracker,
            session_id=session_id,
            user_id=user_id,
            response_text=response_text,
            response_type="recommendation_request_log",
            message_metadata={"stage": "form_start"},
        )
        return []


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
