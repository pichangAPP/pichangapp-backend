from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from rasa_sdk import Tracker

from .context import coerce_metadata
from .time_utils import extract_time_components, infer_date_from_text, infer_time_from_text
from .text_utils import normalize_plain_text

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


def extract_entity_values(tracker: Tracker, entity_name: str) -> List[str]:
    latest_message = tracker.latest_message or {}
    entities = latest_message.get("entities") or []
    values: List[str] = []
    for entity in entities:
        if entity.get("entity") == entity_name and entity.get("value"):
            text = str(entity["value"]).strip()
            if text:
                values.append(text)
    return values


def normalize_location(value: Optional[str]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return value
    cleaned = value.strip()
    return cleaned if cleaned else None


def normalize_sport(value: Optional[str]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return value
    cleaned = value.strip()
    return cleaned if cleaned else None


def normalize_surface(value: Optional[str]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return value
    cleaned = value.strip()
    return cleaned if cleaned else None


def is_noise_answer(value: Optional[str]) -> bool:
    if value is None:
        return True
    normalized = normalize_plain_text(value)
    if not normalized:
        return True
    normalized = normalized.strip()
    if not normalized:
        return True
    if normalized in _NOISE_KEYWORDS:
        return True
    return False


def clean_surface(surface: Optional[str]) -> Optional[str]:
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


def guess_preferences_from_context(tracker: Tracker) -> Dict[str, Optional[str]]:
    latest_message = tracker.latest_message or {}
    metadata = coerce_metadata(latest_message.get("metadata"))
    message_text = latest_message.get("text") or ""

    def _from_metadata(keys: Tuple[str, ...]) -> Optional[str]:
        for key in keys:
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    preferences: Dict[str, Optional[str]] = {}
    provided: Set[str] = set()
    location_values = extract_entity_values(tracker, "location")
    location_source = None
    location_value = tracker.get_slot("preferred_location")
    if is_noise_answer(location_value):
        location_value = None
    else:
        location_source = "slot"
    if not location_value and location_values:
        candidate = location_values[0]
        if not is_noise_answer(candidate):
            location_value = candidate
            location_source = "entity"
    if not location_value:
        meta_location = _from_metadata(("location", "preferred_location", "district"))
        if not is_noise_answer(meta_location):
            location_value = meta_location
            location_source = "metadata"
    normalized_location = normalize_location(location_value)
    if normalized_location:
        preferences["preferred_location"] = normalized_location
        if location_source in {"entity", "metadata"}:
            provided.add("preferred_location")
    sport_values = extract_entity_values(tracker, "sport")
    sport_source = None
    sport_value = tracker.get_slot("preferred_sport")
    if is_noise_answer(sport_value):
        sport_value = None
    else:
        sport_source = "slot"
    if not sport_value and sport_values:
        candidate = sport_values[0]
        if not is_noise_answer(candidate):
            sport_value = candidate
            sport_source = "entity"
    if not sport_value:
        meta_sport = _from_metadata(("sport", "preferred_sport"))
        if not is_noise_answer(meta_sport):
            sport_value = meta_sport
            sport_source = "metadata"
    normalized_sport = normalize_sport(sport_value)
    if normalized_sport:
        preferences["preferred_sport"] = normalized_sport
    else:
        preferences["preferred_sport"] = sport_value
    if sport_value and sport_source in {"entity", "metadata"}:
        provided.add("preferred_sport")

    surface_values = extract_entity_values(tracker, "surface")
    surface_source = None
    surface_value = tracker.get_slot("preferred_surface")
    if is_noise_answer(surface_value):
        surface_value = None
    else:
        surface_source = "slot"
    if not surface_value and surface_values:
        candidate = surface_values[0]
        if not is_noise_answer(candidate):
            surface_value = candidate
            surface_source = "entity"
    if not surface_value:
        meta_surface = _from_metadata(("surface", "preferred_surface"))
        if not is_noise_answer(meta_surface):
            surface_value = meta_surface
            surface_source = "metadata"
    cleaned_surface = clean_surface(surface_value) if surface_value else None
    if cleaned_surface:
        preferences["preferred_surface"] = cleaned_surface
        if surface_source in {"entity", "metadata"}:
            provided.add("preferred_surface")
    date_values = extract_entity_values(tracker, "date")
    date_source = None
    date_value = tracker.get_slot("preferred_date")
    if is_noise_answer(date_value):
        date_value = None
    else:
        date_source = "slot"
    if not date_value and date_values:
        candidate = date_values[0]
        if not is_noise_answer(candidate):
            date_value = candidate
            date_source = "entity"
    if not date_value:
        meta_date = _from_metadata(("preferred_date", "date"))
        if not is_noise_answer(meta_date):
            date_value = meta_date
            date_source = "metadata"
    inferred_date = date_value or infer_date_from_text(message_text)
    if inferred_date:
        preferences["preferred_date"] = inferred_date
        if date_source in {"entity", "metadata"}:
            provided.add("preferred_date")
    time_values = extract_entity_values(tracker, "time")
    time_source = None
    time_value = tracker.get_slot("preferred_start_time")
    if is_noise_answer(time_value):
        time_value = None
    else:
        time_source = "slot"
    if not time_value and time_values:
        candidate = time_values[0]
        if not is_noise_answer(candidate):
            time_value = candidate
            time_source = "entity"
    if not time_value:
        meta_time = _from_metadata(("preferred_start_time", "time"))
        if not is_noise_answer(meta_time):
            time_value = meta_time
            time_source = "metadata"
    inferred_time = time_value or infer_time_from_text(message_text)
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
        components = extract_time_components(preferences["preferred_start_time"])
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


def build_preference_summary(preferences: Dict[str, Optional[str]]) -> Optional[str]:
    fragments: List[str] = []
    provided: Set[str] = preferences.get("_provided", set())  # type: ignore[arg-type]
    location = preferences.get("preferred_location")
    date_value = format_short_date(preferences.get("preferred_date")) if "preferred_date" in provided else None
    start_time = format_short_time(preferences.get("preferred_start_time")) if "preferred_start_time" in provided else None
    end_time = format_short_time(preferences.get("preferred_end_time")) if "preferred_end_time" in provided else None
    surface = clean_surface(preferences.get("preferred_surface")) if "preferred_surface" in provided else None
    sport = preferences.get("preferred_sport") if "preferred_sport" in provided else None

    if location:
        fragments.append(f"en {location}")
    if date_value:
        fragments.append(f"para {date_value}")
    if start_time:
        if end_time and end_time != start_time:
            fragments.append(f"entre las {start_time} y las {end_time}")
        else:
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


def format_short_date(value: Optional[str]) -> Optional[str]:
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


def format_short_time(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    components = extract_time_components(value)
    if components is None:
        return None
    hour, minute = components
    return f"{hour:02d}:{minute:02d}"


def apply_default_preferences(preferences: Dict[str, Optional[str]], metadata: Dict[str, Any]) -> Dict[str, Optional[str]]:
    now = datetime.now(timezone.utc)
    if not preferences.get("preferred_date"):
        preferences["preferred_date"] = now.date().isoformat()
    if not preferences.get("preferred_start_time"):
        rounded = now + timedelta(minutes=30)
        preferences["preferred_start_time"] = rounded.strftime("%H:%M")
    if not preferences.get("preferred_end_time") and preferences.get("preferred_start_time"):
        components = extract_time_components(preferences["preferred_start_time"])
        if components:
            hour, minute = components
            end_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(hours=1)
            preferences["preferred_end_time"] = end_dt.strftime("%H:%M")
    if not preferences.get("preferred_location"):
        default_location = metadata.get("district") or metadata.get("location") or metadata.get("preferred_location")
        if isinstance(default_location, str) and default_location.strip():
            preferences["preferred_location"] = default_location.strip()
    return preferences
