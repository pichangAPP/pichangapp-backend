"""Repositories for admin-related data access and external analytics calls."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import text

from ...infrastructure.config import settings
from ...infrastructure.database import get_connection

LOGGER = logging.getLogger(__name__)


def fetch_managed_campuses(user_id: int) -> List[Dict[str, Any]]:
    query = text(
        """
        SELECT id_campus, name, district, address
        FROM booking.campus
        WHERE id_manager = :user_id
        ORDER BY name
        """
    )
    with get_connection() as connection:
        result = connection.execute(query, {"user_id": user_id})
        campuses: List[Dict[str, Any]] = []
        for row in result:
            mapping = row._mapping
            campuses.append(
                {
                    "id_campus": int(mapping["id_campus"]),
                    "name": mapping.get("name"),
                    "district": mapping.get("district"),
                    "address": mapping.get("address"),
                }
            )
        return campuses


async def fetch_top_clients_from_analytics(
    campus_id: int,
    *,
    token: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    base_url = settings.ANALYTICS_SERVICE_URL.rstrip("/")
    endpoint = f"{base_url}/analytics/campuses/{campus_id}/top-clients"
    headers: Dict[str, str] = {}
    if token:
        normalized = token.strip()
        if not normalized.lower().startswith("bearer "):
            normalized = f"Bearer {normalized}"
        headers["Authorization"] = normalized
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(endpoint, headers=headers or None)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            LOGGER.warning(
                "[AdminTopClients] analytics returned %s for campus=%s attempt=%s: %s",
                exc.response.status_code,
                campus_id,
                attempt + 1,
                exc,
            )
            if exc.response.status_code >= 500 and attempt == 0:
                await asyncio.sleep(0.5)
                continue
        except httpx.RequestError as exc:
            LOGGER.warning(
                "[AdminTopClients] request failed for campus=%s attempt=%s: %s",
                campus_id,
                attempt + 1,
                exc,
            )
            if attempt == 0:
                await asyncio.sleep(0.5)
                continue
        except ValueError as exc:
            LOGGER.warning(
                "[AdminTopClients] invalid JSON for campus=%s attempt=%s: %s",
                campus_id,
                attempt + 1,
                exc,
            )
            if attempt == 0:
                await asyncio.sleep(0.25)
                continue
    return None


async def fetch_field_usage_from_analytics(
    campus_id: int,
    *,
    token: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    base_url = settings.ANALYTICS_SERVICE_URL.rstrip("/")
    endpoint = f"{base_url}/analytics/campuses/{campus_id}/top-fields"
    headers: Dict[str, str] = {}
    if token:
        normalized = token.strip()
        if not normalized.lower().startswith("bearer "):
            normalized = f"Bearer {normalized}"
        headers["Authorization"] = normalized
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(endpoint, headers=headers or None)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            LOGGER.warning(
                "[AdminFieldUsage] analytics returned %s for campus=%s attempt=%s: %s",
                exc.response.status_code,
                campus_id,
                attempt + 1,
                exc,
            )
            if exc.response.status_code >= 500 and attempt == 0:
                await asyncio.sleep(0.5)
                continue
        except httpx.RequestError as exc:
            LOGGER.warning(
                "[AdminFieldUsage] request failed for campus=%s attempt=%s: %s",
                campus_id,
                attempt + 1,
                exc,
            )
            if attempt == 0:
                await asyncio.sleep(0.5)
                continue
        except ValueError as exc:
            LOGGER.warning(
                "[AdminFieldUsage] invalid JSON from analytics for campus=%s attempt=%s: %s",
                campus_id,
                attempt + 1,
                exc,
            )
            if attempt == 0:
                await asyncio.sleep(0.25)
                continue
    return None
