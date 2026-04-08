from __future__ import annotations

from datetime import date, datetime, time as time_of_day, timezone
from typing import Any, Dict, List, Optional, Tuple
from .time_utils import (
    ensure_datetime_timezone,
    parse_datetime_value,
)



def rent_start_time(rent: Dict[str, Any]) -> Optional[datetime]:
    start = parse_datetime_value(rent.get("start_time"))
    if start is not None:
        return ensure_datetime_timezone(start)
    schedule = rent.get("schedule") or {}
    return ensure_datetime_timezone(parse_datetime_value(schedule.get("start_time")))


def rent_end_time(rent: Dict[str, Any]) -> Optional[datetime]:
    end = parse_datetime_value(rent.get("end_time"))
    if end is not None:
        return ensure_datetime_timezone(end)
    schedule = rent.get("schedule") or {}
    return ensure_datetime_timezone(parse_datetime_value(schedule.get("end_time")))


def normalize_reservation_status(status: Any) -> str:
    if status is None:
        return ""
    if isinstance(status, str):
        return status.strip().lower()
    return str(status).strip().lower()


def select_target_rent(
    history: List[Dict[str, Any]],
    requested_date: Optional[date],
    requested_time: Optional[time_of_day],
) -> Tuple[Optional[Dict[str, Any]], str]:
    annotated: List[Tuple[Dict[str, Any], Optional[datetime]]] = []
    for rent in history:
        if normalize_reservation_status(rent.get("status")) != "reserved":
            continue
        annotated.append((rent, rent_start_time(rent)))
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


def match_slot_status(
    slots: List[Dict[str, Any]],
    target_start: Optional[datetime],
) -> Optional[str]:
    if not slots or target_start is None:
        return None
    target = ensure_datetime_timezone(target_start)
    for slot in slots:
        slot_start = parse_datetime_value(slot.get("start_time"))
        slot_start = ensure_datetime_timezone(slot_start)
        if slot_start == target:
            status_value = slot.get("status")
            if isinstance(status_value, str):
                return status_value.strip()
            return str(status_value) if status_value is not None else None
    return None


def describe_slot_availability(status: Optional[str]) -> str:
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

