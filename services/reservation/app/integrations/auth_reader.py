"""HTTP-based access to auth user data."""

from __future__ import annotations

import logging
from typing import Iterable, Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.schedule import UserSummary

logger = logging.getLogger(__name__)


class AuthReaderError(RuntimeError):
    """Raised when auth service lookups cannot be completed."""


def _get_auth_base_url() -> str:
    base_url = settings.AUTH_SERVICE_URL.rstrip("/")
    if not base_url:
        raise AuthReaderError("Auth service URL not configured")
    return base_url


def _get_auth_headers() -> dict[str, str]:
    api_key = settings.AUTH_INTERNAL_API_KEY
    if not api_key:
        raise AuthReaderError("Auth internal API key not configured")
    return {"X-Internal-Auth": api_key}


def get_user_summary(db: Session, user_id: int) -> Optional[UserSummary]:
    del db
    url = f"{_get_auth_base_url()}/api/pichangapp/v1/internal/users/{user_id}"
    try:
        response = httpx.get(
            url,
            headers=_get_auth_headers(),
            timeout=settings.AUTH_SERVICE_TIMEOUT,
        )
    except httpx.RequestError as exc:
        logger.warning("Auth service unavailable while fetching user %s: %s", user_id, exc)
        raise AuthReaderError("Auth service unavailable") from exc

    if response.status_code == 404:
        return None
    if response.is_error:
        raise AuthReaderError(f"Auth service error ({response.status_code})")

    payload = response.json()
    return UserSummary(
        id_user=payload["id_user"],
        name=payload["name"],
        lastname=payload["lastname"],
        email=payload["email"],
        phone=payload["phone"],
        imageurl=payload.get("imageurl"),
        status=payload["status"],
    )


def get_user_summaries(
    db: Session,
    user_ids: Iterable[int],
) -> dict[int, UserSummary]:
    del db
    unique_ids = {user_id for user_id in user_ids if user_id is not None}
    if not unique_ids:
        return {}

    url = f"{_get_auth_base_url()}/api/pichangapp/v1/internal/users"
    try:
        response = httpx.get(
            url,
            headers=_get_auth_headers(),
            params={"ids": list(unique_ids)},
            timeout=settings.AUTH_SERVICE_TIMEOUT,
        )
    except httpx.RequestError as exc:
        logger.warning("Auth service unavailable while fetching users: %s", exc)
        raise AuthReaderError("Auth service unavailable") from exc

    if response.is_error:
        raise AuthReaderError(f"Auth service error ({response.status_code})")

    users = response.json()
    return {
        user["id_user"]: UserSummary(
            id_user=user["id_user"],
            name=user["name"],
            lastname=user["lastname"],
            email=user["email"],
            phone=user["phone"],
            imageurl=user.get("imageurl"),
            status=user["status"],
        )
        for user in users
    }


__all__ = ["AuthReaderError", "get_user_summary", "get_user_summaries"]
