"""Error codes and helpers for Auth service."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, status


@dataclass(frozen=True)
class ErrorCode:
    code: str
    message: str
    status_code: int = status.HTTP_400_BAD_REQUEST


AUTH_BAD_REQUEST = ErrorCode(
    code="AUTH_BAD_REQUEST",
    message="Solicitud inválida.",
)
AUTH_CONFLICT = ErrorCode(
    code="AUTH_CONFLICT",
    message="Conflicto en la solicitud.",
    status_code=status.HTTP_409_CONFLICT,
)
AUTH_INTERNAL_ERROR = ErrorCode(
    code="AUTH_INTERNAL_ERROR",
    message="No se pudo procesar la solicitud.",
    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
)
AUTH_SERVICE_UNAVAILABLE = ErrorCode(
    code="AUTH_SERVICE_UNAVAILABLE",
    message="Servicio no disponible.",
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
)

USER_NOT_FOUND = ErrorCode(
    code="USER_NOT_FOUND",
    message="Usuario no encontrado.",
    status_code=status.HTTP_404_NOT_FOUND,
)
ROLE_NOT_FOUND = ErrorCode(
    code="ROLE_NOT_FOUND",
    message="Rol no encontrado.",
    status_code=status.HTTP_404_NOT_FOUND,
)
EMAIL_ALREADY_REGISTERED = ErrorCode(
    code="EMAIL_ALREADY_REGISTERED",
    message="El correo ya está registrado.",
    status_code=status.HTTP_409_CONFLICT,
)

INVALID_CREDENTIALS = ErrorCode(
    code="INVALID_CREDENTIALS",
    message="Credenciales inválidas.",
    status_code=status.HTTP_401_UNAUTHORIZED,
)
INVALID_REFRESH_TOKEN = ErrorCode(
    code="INVALID_REFRESH_TOKEN",
    message="Refresh token inválido.",
    status_code=status.HTTP_401_UNAUTHORIZED,
)

INVALID_GOOGLE_TOKEN = ErrorCode(
    code="INVALID_GOOGLE_TOKEN",
    message="Token de Google inválido.",
    status_code=status.HTTP_401_UNAUTHORIZED,
)
EXPIRED_GOOGLE_TOKEN = ErrorCode(
    code="EXPIRED_GOOGLE_TOKEN",
    message="Token de Google expirado.",
    status_code=status.HTTP_401_UNAUTHORIZED,
)
REVOKED_GOOGLE_TOKEN = ErrorCode(
    code="REVOKED_GOOGLE_TOKEN",
    message="Token de Google revocado.",
    status_code=status.HTTP_401_UNAUTHORIZED,
)
GOOGLE_EMAIL_MISSING = ErrorCode(
    code="GOOGLE_EMAIL_MISSING",
    message="El token de Google no contiene email.",
    status_code=status.HTTP_400_BAD_REQUEST,
)
DEFAULT_ROLE_NOT_CONFIGURED = ErrorCode(
    code="DEFAULT_ROLE_NOT_CONFIGURED",
    message="Rol por defecto no configurado.",
    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
)

INTERNAL_API_KEY_MISSING = ErrorCode(
    code="INTERNAL_API_KEY_MISSING",
    message="Internal API key no configurado.",
    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
)
INVALID_INTERNAL_CREDENTIALS = ErrorCode(
    code="INVALID_INTERNAL_CREDENTIALS",
    message="Credenciales internas inválidas.",
    status_code=status.HTTP_401_UNAUTHORIZED,
)


def http_error(error: ErrorCode, *, detail: Optional[str] = None) -> HTTPException:
    payload: dict[str, object] = {"code": error.code, "message": error.message}
    if detail:
        payload["detail"] = detail
    return HTTPException(status_code=error.status_code, detail=payload)
