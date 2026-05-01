"""Repositories for admin-related data access and external analytics calls."""

from __future__ import annotations

import logging
from datetime import date
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
    traffic_mode: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    return await analytics_client.get_campus_metrics(
        campus_id, token=token, traffic_mode=traffic_mode
    )


async def fetch_active_reservations_from_analytics(
    campus_id: int,
    *,
    token: Optional[str] = None,
    target_date: Optional[date] = None,
    field_name: Optional[str] = None,
    limit: int = 100,
) -> Optional[Dict[str, Any]]:
    return await analytics_client.get_active_reservations(
        campus_id,
        token=token,
        target_date=target_date,
        field_name=field_name,
        limit=limit,
    )


async def fetch_rent_metrics_from_analytics(
    *,
    token: Optional[str] = None,
    period: str = "today",
    group_by: str = "day",
    target_date: Optional[date] = None,
    campus_id: Optional[int] = None,
    field_id: Optional[int] = None,
    sport_id: Optional[int] = None,
    status: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    return await analytics_client.get_rent_metrics(
        token=token,
        period=period,
        group_by=group_by,
        target_date=target_date,
        campus_id=campus_id,
        field_id=field_id,
        sport_id=sport_id,
        status=status,
    )


def resolve_field_id_by_name(campus_id: int, field_name: str) -> Optional[int]:
    normalized = (field_name or "").strip()
    if not normalized:
        return None
    query = text(
        """
        SELECT id_field
        FROM booking.field
        WHERE id_campus = :campus_id
          AND (
            LOWER(name) = LOWER(:field_name_exact)
            OR LOWER(name) LIKE LOWER(:field_name_like)
          )
        ORDER BY CASE WHEN LOWER(name) = LOWER(:field_name_exact) THEN 0 ELSE 1 END
        LIMIT 1
        """
    )
    params = {
        "campus_id": campus_id,
        "field_name_exact": normalized,
        "field_name_like": f"%{normalized}%",
    }
    with get_connection() as connection:
        row = connection.execute(query, params).fetchone()
    if not row:
        return None
    return int(row._mapping["id_field"])


def resolve_sport_id_by_name(sport_name: str) -> Optional[int]:
    normalized = (sport_name or "").strip()
    if not normalized:
        return None
    query = text(
        """
        SELECT id_sport
        FROM booking.sports
        WHERE LOWER(sport_name) = LOWER(:sport_exact)
           OR LOWER(sport_name) LIKE LOWER(:sport_like)
        ORDER BY CASE WHEN LOWER(sport_name) = LOWER(:sport_exact) THEN 0 ELSE 1 END
        LIMIT 1
        """
    )
    params = {
        "sport_exact": normalized,
        "sport_like": f"%{normalized}%",
    }
    with get_connection() as connection:
        row = connection.execute(query, params).fetchone()
    if not row:
        return None
    return int(row._mapping["id_sport"])
