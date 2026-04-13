"""Repositories for reservation-service HTTP integrations."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

import httpx

from ...infrastructure.config import settings

LOGGER = logging.getLogger(__name__)


def build_reservation_headers(token: Optional[str]) -> Optional[Dict[str, str]]:
    if not token:
        return None
    normalized = token.strip()
    if not normalized:
        return None
    if not normalized.lower().startswith("bearer "):
        normalized = f"Bearer {normalized}"
    return {"Authorization": normalized}


async def fetch_user_rent_history(
    user_id: int,
    *,
    token: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    base_url = settings.RESERVATION_SERVICE_URL.rstrip("/")
    endpoint = f"{base_url}/rents/users/{user_id}/history"
    headers = build_reservation_headers(token)
    params: Dict[str, Any] = {}
    if status:
        params["status"] = status
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                endpoint, headers=headers or None, params=params or None
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        LOGGER.warning(
            "[ReservationHistory] status=%s user=%s status_filter=%s: %s",
            exc.response.status_code,
            user_id,
            status,
            exc,
        )
    except httpx.RequestError as exc:
        LOGGER.warning(
            "[ReservationHistory] request failed for user=%s status_filter=%s: %s",
            user_id,
            status,
            exc,
        )
    except ValueError as exc:
        LOGGER.warning(
            "[ReservationHistory] invalid JSON for user=%s status_filter=%s: %s",
            user_id,
            status,
            exc,
        )
    return []


async def fetch_schedule_time_slots(
    field_id: int,
    target_date: date,
    *,
    token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    base_url = settings.RESERVATION_SERVICE_URL.rstrip("/")
    endpoint = f"{base_url}/schedules/time-slots"
    headers = build_reservation_headers(token)
    params = {"field_id": field_id, "date": target_date.isoformat()}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(endpoint, headers=headers or None, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        LOGGER.warning(
            "[ScheduleSlots] status=%s field=%s date=%s: %s",
            exc.response.status_code,
            field_id,
            target_date,
            exc,
        )
    except httpx.RequestError as exc:
        LOGGER.warning(
            "[ScheduleSlots] request failed for field=%s date=%s: %s",
            field_id,
            target_date,
            exc,
        )
    except ValueError as exc:
        LOGGER.warning(
            "[ScheduleSlots] invalid JSON for field=%s date=%s: %s",
            field_id,
            target_date,
            exc,
        )
    return []
