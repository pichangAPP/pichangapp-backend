"""Error codes and helpers for Reservation service."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, status


@dataclass(frozen=True)
class ErrorCode:
    code: str
    message: str
    status_code: int = status.HTTP_400_BAD_REQUEST


SCHEDULE_PAST_START = ErrorCode(
    code="SCHEDULE_PAST_START",
    message="El horario ya comenzó. Elige otro horario.",
)
SCHEDULE_INVALID_TIME_RANGE = ErrorCode(
    code="SCHEDULE_INVALID_TIME_RANGE",
    message="La hora de fin debe ser mayor a la hora de inicio.",
)
SCHEDULE_CROSS_DAY = ErrorCode(
    code="SCHEDULE_CROSS_DAY",
    message="El horario no puede cruzar al día siguiente.",
)
SCHEDULE_OUTSIDE_OPENING_HOURS = ErrorCode(
    code="SCHEDULE_OUTSIDE_OPENING_HOURS",
    message="El horario debe estar dentro del horario de apertura del campo.",
)
SCHEDULE_TIME_ALIGNMENT = ErrorCode(
    code="SCHEDULE_TIME_ALIGNMENT",
    message="El horario debe iniciar en el minuto permitido por la apertura del campo.",
)
SCHEDULE_DURATION_NOT_HOURS = ErrorCode(
    code="SCHEDULE_DURATION_NOT_HOURS",
    message="La duración del horario debe ser de 1 hora o múltiplos.",
)
SCHEDULE_CONFLICT = ErrorCode(
    code="SCHEDULE_CONFLICT",
    message="El campo ya tiene un horario en ese rango.",
    status_code=status.HTTP_409_CONFLICT,
)
SCHEDULE_WEEKLY_CLOSURE = ErrorCode(
    code="SCHEDULE_WEEKLY_CLOSURE",
    message="Este horario no está disponible por un cierre recurrente del campus o cancha.",
    status_code=status.HTTP_409_CONFLICT,
)
RENT_ACTIVE_CONFLICT = ErrorCode(
    code="RENT_ACTIVE_CONFLICT",
    message="El campo ya tiene una reserva activa en ese rango.",
    status_code=status.HTTP_409_CONFLICT,
)
RENT_SCHEDULE_STARTED = ErrorCode(
    code="RENT_SCHEDULE_STARTED",
    message="La reserva ya comenzó. Elige otro horario.",
)
SCHEDULE_NOT_FOUND = ErrorCode(
    code="SCHEDULE_NOT_FOUND",
    message="Horario no encontrado.",
    status_code=status.HTTP_404_NOT_FOUND,
)
FIELD_NOT_FOUND = ErrorCode(
    code="FIELD_NOT_FOUND",
    message="Cancha no encontrada.",
    status_code=status.HTTP_404_NOT_FOUND,
)
USER_NOT_FOUND = ErrorCode(
    code="USER_NOT_FOUND",
    message="Usuario no encontrado.",
    status_code=status.HTTP_404_NOT_FOUND,
)
RENT_NOT_FOUND = ErrorCode(
    code="RENT_NOT_FOUND",
    message="Reserva no encontrada.",
    status_code=status.HTTP_404_NOT_FOUND,
)
PAYMENT_NOT_FOUND = ErrorCode(
    code="PAYMENT_NOT_FOUND",
    message="Pago no encontrado.",
    status_code=status.HTTP_404_NOT_FOUND,
)
STATUS_NOT_FOUND = ErrorCode(
    code="STATUS_NOT_FOUND",
    message="Estado no encontrado.",
    status_code=status.HTTP_404_NOT_FOUND,
)


def http_error(error: ErrorCode, *, detail: Optional[str] = None) -> HTTPException:
    payload: dict[str, object] = {"code": error.code, "message": error.message}
    if detail:
        payload["detail"] = detail
    return HTTPException(status_code=error.status_code, detail=payload)
