from __future__ import annotations

import re
from typing import List, Optional, Tuple

from rasa_sdk import Tracker

from .context import coerce_metadata
from .preferences import is_noise_answer

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

_BUDGET_RANGE_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"entre\s*(\d+(?:[.,]\d+)?)\s*(?:y|e|a|-)\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE),
    re.compile(r"(?:de|desde)\s*(\d+(?:[.,]\d+)?)\s*(?:a|-)\s*(\d+(?:[.,]\d+)?)\s*(?:soles?|s/\.?|s/|\$)?", re.IGNORECASE),
    re.compile(r"(?:s/\.?|s/|\$)\s*(\d+(?:[.,]\d+)?)\s*-\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE),
)
_BUDGET_MAX_PATTERN = re.compile(
    r"(?:hasta|máximo|maximo|tope|menos de|menor a|presupuesto(?:\s+de)?|budget(?:\s+de)?|precio(?:\s+tope)?)\s*(\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)
_BUDGET_MIN_PATTERN = re.compile(
    r"(?:desde|mínimo|minimo|más de|mas de|mayor a|superior a)\s*(\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)
_BUDGET_GENERIC_PATTERN = re.compile(r"(?:s/\.?|s/|\$)\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)
_BUDGET_SOL_PATTERN = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:soles|lucas)", re.IGNORECASE)


def _mentions_price_context(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in _PRICE_CONTEXT_KEYWORDS)


def detect_price_focus(text: Optional[str]) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(keyword in lowered for keyword in _PRICE_PRIORITY_KEYWORDS)


def detect_rating_focus(text: Optional[str]) -> bool:
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


def parse_budget_from_text(text: Optional[str], *, force: bool = False) -> Tuple[Optional[float], Optional[float]]:
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


def format_budget_range(min_price: Optional[float], max_price: Optional[float]) -> Optional[str]:
    if min_price is not None and max_price is not None:
        return f"con presupuesto entre S/ {min_price:.2f} y S/ {max_price:.2f}"
    if max_price is not None:
        return f"con presupuesto hasta S/ {max_price:.2f}"
    if min_price is not None:
        return f"con presupuesto desde S/ {min_price:.2f}"
    return None


def extract_budget_preferences(tracker: Tracker) -> Tuple[Optional[float], Optional[float], bool]:
    latest_message = tracker.latest_message or {}
    metadata = coerce_metadata(latest_message.get("metadata"))
    message_text = latest_message.get("text") or ""
    price_focus = detect_price_focus(message_text)

    candidate_texts: List[Tuple[str, bool]] = []
    slot_budget = tracker.get_slot("preferred_budget")
    if slot_budget and not is_noise_answer(slot_budget):
        candidate_texts.append((str(slot_budget), True))

    metadata_budget = metadata.get("budget") or metadata.get("preferred_budget")
    if metadata_budget and not is_noise_answer(metadata_budget):
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
        low, high = parse_budget_from_text(text_value, force=force)
        if low is not None:
            min_price = low if min_price is None else max(min_price, low)
        if high is not None:
            max_price = high if max_price is None else min(max_price, high)

    return min_price, max_price, price_focus
