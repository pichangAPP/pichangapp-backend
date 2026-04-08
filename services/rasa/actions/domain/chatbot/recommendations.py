from __future__ import annotations

from datetime import time as time_of_day
import re
from typing import Any, Dict, List, Optional, Set

_FIELD_SIZE_THRESHOLDS = (900.0, 1500.0)


def _parse_measurement_area(measurement: Optional[str]) -> Optional[float]:
    if not measurement:
        return None
    normalized = measurement.lower().replace("m", "").replace("metros", "")
    normalized = normalized.replace(" ", "")
    parts = re.split(r"[x×]", normalized)
    if len(parts) < 2:
        return None
    try:
        width = float(parts[0].replace(",", "."))
        height = float(parts[1].replace(",", "."))
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return width * height


def field_size_label(measurement: Optional[str]) -> Optional[str]:
    area = _parse_measurement_area(measurement)
    if area is None:
        return None
    small_threshold, medium_threshold = _FIELD_SIZE_THRESHOLDS
    if area < small_threshold:
        return "pequeña"
    if area <= medium_threshold:
        return "mediana"
    return "grande"


def describe_field_size(measurement: Optional[str]) -> Optional[str]:
    label = field_size_label(measurement)
    if not label:
        return None
    clean_measurement = measurement.strip() if measurement else ""
    if clean_measurement:
        return f"Tamaño {label} ({clean_measurement})"
    return f"Tamaño {label}"


def _time_to_string(value: Optional[time_of_day]) -> Optional[str]:
    return value.strftime("%H:%M") if value else None


def serialize_filter_payload(
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


def normalize_sport_preference(value: Optional[str]) -> Optional[str]:
    """Normalize sport values (NLU synonyms are expected to handle aliases)."""
    if not value or not isinstance(value, str):
        return value
    cleaned = value.strip()
    return cleaned if cleaned else None


def normalize_surface_preference(value: Optional[str]) -> Optional[str]:
    """Normalize surface values (NLU synonyms are expected to handle aliases)."""
    if not value or not isinstance(value, str):
        return value
    cleaned = value.strip()
    return cleaned if cleaned else None


def describe_relaxations(
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

