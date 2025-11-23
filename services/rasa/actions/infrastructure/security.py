"""Utilities to decode JWT tokens for the action server."""

from __future__ import annotations

import logging
from typing import Any, Dict

from jose import JWTError, jwt

from .config import settings

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
        LOGGER.debug("Decoded token payload keys: %s", list(payload.keys()))
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


__all__ = ["TokenDecodeError", "decode_access_token", "extract_role_from_claims"]
