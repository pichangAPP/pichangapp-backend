from __future__ import annotations

import logging
import re
from datetime import date, datetime, time as time_of_day, timedelta, timezone
from typing import Any, Optional, Tuple

from zoneinfo import ZoneInfo

from .text_utils import normalize_plain_text

LOGGER = logging.getLogger(__name__)

LIMA_TZ = ZoneInfo("America/Lima")

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

_DAY_KEYWORDS = {
    "hoy": 0,
    "esta noche": 0,
    "esta tarde": 0,
    "manana": 1,
    "mañana": 1,
    "pasado manana": 2,
    "fin de semana": 2,
}

_DAYPART_HINTS = {
    "madrugada": "06:00",
    "temprano": "08:00",
    "manana": "09:00",
    "mañana": "09:00",
    "medio dia": "12:00",
    "mediodia": "12:00",
    "tarde": "17:00",
    "noche": "20:00",
}

_TIME_RANGE_PATTERN = re.compile(
    r"entre\s+(\d{1,2}(?::\d{2})?)\s*(?:y|a|al?)\s*(\d{1,2}(?::\d{2})?)",
    re.IGNORECASE,
)
_TIME_WITH_KEYWORD_PATTERN = re.compile(
    r"(?:a|para|al?)\s+(?:las?\s*)?(\d{1,2}(?::\d{2})?)(?:\s*(am|pm))?",
    re.IGNORECASE,
)


def parse_datetime_value(value: Any) -> Optional[datetime]:
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


def parse_date_value(value: Optional[str]) -> Optional[date]:
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


def parse_time_value(value: Optional[str]) -> Optional[time_of_day]:
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


def ensure_datetime_timezone(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def extract_time_components(time_value: Optional[str]) -> Optional[Tuple[int, int]]:
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


def coerce_time_value(time_value: Optional[str]) -> Optional[time_of_day]:
    components = extract_time_components(time_value)
    if not components:
        return None
    hour, minute = components
    try:
        return time_of_day(hour=hour, minute=minute)
    except ValueError:
        return None


def parse_time_token(token: str) -> Optional[str]:
    normalized = token.strip()
    if not normalized:
        return None
    components = extract_time_components(normalized)
    if not components:
        return None
    hour, minute = components
    normalized_lower = normalized.lower()
    if "am" in normalized_lower or "a.m." in normalized_lower:
        hour = hour % 12
    elif "pm" in normalized_lower or "p.m." in normalized_lower:
        hour = hour % 12 + 12
    else:
        now = datetime.now(LIMA_TZ)
        if hour < 12 and now.hour >= 12:
            hour += 12
    return f"{hour:02d}:{minute:02d}"


def infer_date_from_text(text: str) -> Optional[str]:
    normalized = normalize_plain_text(text)
    if not normalized:
        return None
    base_date = datetime.now(timezone.utc).date()
    for keyword, offset in _DAY_KEYWORDS.items():
        if keyword in normalized:
            return (base_date + timedelta(days=offset)).isoformat()
    return None


def infer_time_from_text(text: str) -> Optional[str]:
    normalized = normalize_plain_text(text)
    if not normalized:
        return None
    range_match = _TIME_RANGE_PATTERN.search(normalized)
    if range_match:
        start_token = range_match.group(1)
        parsed = parse_time_token(start_token)
        if parsed:
            return parsed
    keyword_match = _TIME_WITH_KEYWORD_PATTERN.search(normalized)
    if keyword_match:
        token = keyword_match.group(1)
        suffix = keyword_match.group(2) or ""
        parsed = parse_time_token(token + (" " + suffix if suffix else ""))
        if parsed:
            return parsed
    for keyword, time_hint in _DAYPART_HINTS.items():
        if keyword in normalized:
            return time_hint
    return None


def parse_datetime(date_value: Optional[str], time_value: Optional[str]) -> datetime:
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
                    LOGGER.debug(
                        "[TimeParser] Using current date because date_value=%s is invalid",
                        date_value,
                    )
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
        time_components = extract_time_components(time_value)
        if time_components is None:
            LOGGER.debug(
                "[TimeParser] Falling back to existing hour for time_value=%s",
                time_value,
            )
            return date_part
        hour, minute = time_components
        date_part = date_part.replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )
    return date_part


def coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        for fmt in (
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                dt = datetime.strptime(value, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
    return datetime.now(timezone.utc)

