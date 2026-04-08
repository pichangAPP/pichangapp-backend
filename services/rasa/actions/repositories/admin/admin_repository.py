"""Repositories for admin-related data access and external analytics calls."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import text

from ...infrastructure.clients.analytics_client import analytics_client
from ...infrastructure.database import get_connection

LOGGER = logging.getLogger(__name__)


def fetch_managed_campuses(user_id: int) -> List[Dict[str, Any]]:
    LOGGER.info("[AdminRepository] Fetching campuses for manager user_id=%s", user_id)
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
        LOGGER.info(
            "[AdminRepository] Found %s campuses for manager user_id=%s",
            len(campuses),
            user_id,
        )
        return campuses


async def fetch_top_clients_from_analytics(
    campus_id: int,
    *,
    token: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    return await analytics_client.get_top_clients(campus_id, token=token)


async def fetch_field_usage_from_analytics(
    campus_id: int,
    *,
    token: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    return await analytics_client.get_top_fields(campus_id, token=token)


async def fetch_revenue_metrics_from_analytics(
    campus_id: int,
    *,
    token: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    return await analytics_client.get_campus_metrics(campus_id, token=token)
