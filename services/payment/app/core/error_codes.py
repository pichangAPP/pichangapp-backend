"""Error codes and helpers for Payment service."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, status


@dataclass(frozen=True)
class ErrorCode:
    code: str
    message: str
    status_code: int = status.HTTP_400_BAD_REQUEST


PAYMENT_NOT_FOUND = ErrorCode(
    code="PAYMENT_NOT_FOUND",
    message="Pago no encontrado.",
    status_code=status.HTTP_404_NOT_FOUND,
)
PAYMENT_INVALID_STATUS = ErrorCode(
    code="PAYMENT_INVALID_STATUS",
    message="Estado de pago inválido.",
    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
)
PAYMENT_MISSING_RENT_ID = ErrorCode(
    code="PAYMENT_MISSING_RENT_ID",
    message="Falta rent_id para el método de pago.",
    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
)
PAYMENT_MISSING_PAYER_PHONE = ErrorCode(
    code="PAYMENT_MISSING_PAYER_PHONE",
    message="Falta el teléfono del pagador.",
    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
)
PAYMENT_MISSING_APPROVAL_CODE = ErrorCode(
    code="PAYMENT_MISSING_APPROVAL_CODE",
    message="Falta el código de aprobación.",
    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
)
RENT_NOT_FOUND = ErrorCode(
    code="RENT_NOT_FOUND",
    message="Reserva no encontrada.",
    status_code=status.HTTP_404_NOT_FOUND,
)
FIELD_NOT_FOUND = ErrorCode(
    code="FIELD_NOT_FOUND",
    message="Cancha/campus no encontrado.",
    status_code=status.HTTP_404_NOT_FOUND,
)
PAYMENT_RECEIVER_NOT_CONFIGURED = ErrorCode(
    code="PAYMENT_RECEIVER_NOT_CONFIGURED",
    message="No hay receptor de pago configurado para el campus.",
    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
)
PAYMENT_METHODS_NOT_FOUND = ErrorCode(
    code="PAYMENT_METHODS_NOT_FOUND",
    message="Configuración de métodos de pago no encontrada.",
    status_code=status.HTTP_404_NOT_FOUND,
)
PAYMENT_METHODS_EXISTS = ErrorCode(
    code="PAYMENT_METHODS_EXISTS",
    message="Ya existe configuración de métodos de pago para ese negocio/campus.",
    status_code=status.HTTP_409_CONFLICT,
)
PAYMENT_METHODS_INVALID = ErrorCode(
    code="PAYMENT_METHODS_INVALID",
    message="Configuración de métodos de pago inválida.",
    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
)


def http_error(error: ErrorCode, *, detail: Optional[str] = None) -> HTTPException:
    payload: dict[str, object] = {"code": error.code, "message": error.message}
    if detail:
        payload["detail"] = detail
    return HTTPException(status_code=error.status_code, detail=payload)

