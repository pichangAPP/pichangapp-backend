"""Security helpers shared by the chatbot API and Rasa actions."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)
LOGGER = logging.getLogger(__name__)


class TokenDecodeError(RuntimeError):
    """Raised when an access token cannot be decoded."""


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode a JWT access token using the shared auth secret."""

    if not token:
        raise TokenDecodeError("Token must not be empty")

    normalized = token.strip()
    if normalized.lower().startswith("bearer "):
        normalized = normalized[7:].strip()

    try:
        payload = jwt.decode(
            normalized,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        LOGGER.debug("Decoded token payload keys: %%s", list(payload.keys()))
        return payload
    except JWTError as exc:  # pragma: no cover - logging side effects
        LOGGER.exception("Failed to decode JWT: %s", exc)
        raise TokenDecodeError("Invalid or expired token") from exc


def extract_role_from_claims(payload: Dict[str, Any]) -> str | None:
    """Return the textual role representation from JWT claims."""

    raw_role = payload.get("id_role")
    if raw_role is None:
        return None
    try:
        role_id = int(raw_role)
    except (TypeError, ValueError):
        LOGGER.warning("Unexpected role claim type: %s", raw_role)
        return None

    if role_id == 2:
        return "admin"
    if role_id == 1:
        return "player"
    LOGGER.info("Unknown role id in token: %s", role_id)
    return None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """Validate the bearer token issued by the Auth service."""

    if (
        credentials is None
        or not credentials.scheme
        or credentials.scheme.lower() != "bearer"
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        payload = decode_access_token(token)
    except TokenDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return payload


__all__ = [
    "TokenDecodeError",
    "decode_access_token",
    "extract_role_from_claims",
    "get_current_user",
]
