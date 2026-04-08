"""Error codes and helpers for Analytics service."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, status


@dataclass(frozen=True)
class ErrorCode:
    code: str
    message: str
    status_code: int = status.HTTP_400_BAD_REQUEST


ANALYTICS_INVALID_DATE_RANGE = ErrorCode(
    code="ANALYTICS_INVALID_DATE_RANGE",
    message="La fecha de inicio debe ser menor o igual a la fecha de fin.",
)
ANALYTICS_INVALID_LIMIT = ErrorCode(
    code="ANALYTICS_INVALID_LIMIT",
    message="El límite debe estar entre 1 y 100.",
)
CAMPUS_NOT_FOUND = ErrorCode(
    code="CAMPUS_NOT_FOUND",
    message="Campus no encontrado.",
    status_code=status.HTTP_404_NOT_FOUND,
)
FEEDBACK_NOT_FOUND = ErrorCode(
    code="FEEDBACK_NOT_FOUND",
    message="Feedback no encontrado.",
    status_code=status.HTTP_404_NOT_FOUND,
)
RENT_NOT_FOUND = ErrorCode(
    code="RENT_NOT_FOUND",
    message="Reserva no encontrada.",
    status_code=status.HTTP_404_NOT_FOUND,
)
FEEDBACK_FORBIDDEN = ErrorCode(
    code="FEEDBACK_FORBIDDEN",
    message="No tienes permiso para esta acción.",
    status_code=status.HTTP_403_FORBIDDEN,
)
FEEDBACK_NOT_ALLOWED = ErrorCode(
    code="FEEDBACK_NOT_ALLOWED",
    message="El feedback solo puede enviarse después de terminar la reserva.",
)
FEEDBACK_ALREADY_SUBMITTED = ErrorCode(
    code="FEEDBACK_ALREADY_SUBMITTED",
    message="El feedback ya fue enviado para esta reserva.",
    status_code=status.HTTP_409_CONFLICT,
)
ANALYTICS_REPOSITORY_ERROR = ErrorCode(
    code="ANALYTICS_REPOSITORY_ERROR",
    message="No se pudo completar la operación de analíticas.",
    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
)


def http_error(error: ErrorCode, *, detail: Optional[str] = None) -> HTTPException:
    payload: dict[str, object] = {"code": error.code, "message": error.message}
    if detail:
        payload["detail"] = detail
    return HTTPException(status_code=error.status_code, detail=payload)

