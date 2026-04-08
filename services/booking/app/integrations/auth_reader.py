"""HTTP-based access to auth user data."""

from __future__ import annotations

import logging
from typing import Iterable, Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.manager import ManagerResponse

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


def get_manager_summary(db: Session, manager_id: int) -> Optional[ManagerResponse]:
    del db
    url = f"{_get_auth_base_url()}/api/pichangapp/v1/internal/users/{manager_id}"
    try:
        response = httpx.get(
            url,
            headers=_get_auth_headers(),
            timeout=settings.AUTH_SERVICE_TIMEOUT,
        )
    except httpx.RequestError as exc:
        logger.warning("Auth service unavailable while fetching manager %s: %s", manager_id, exc)
        raise AuthReaderError("Auth service unavailable") from exc

    if response.status_code == 404:
        return None
    if response.is_error:
        raise AuthReaderError(f"Auth service error ({response.status_code})")

    payload = response.json()
    return ManagerResponse(**payload)


def get_manager_summaries(
    db: Session,
    manager_ids: Iterable[int],
) -> dict[int, ManagerResponse]:
    del db
    unique_ids = {manager_id for manager_id in manager_ids if manager_id is not None}
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
        logger.warning("Auth service unavailable while fetching managers: %s", exc)
        raise AuthReaderError("Auth service unavailable") from exc

    if response.is_error:
        raise AuthReaderError(f"Auth service error ({response.status_code})")

    users = response.json()
    return {user["id_user"]: ManagerResponse(**user) for user in users}


__all__ = ["AuthReaderError", "get_manager_summary", "get_manager_summaries"]
