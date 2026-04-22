"""Async client for Analytics service endpoints."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx

from ..config import settings

LOGGER = logging.getLogger(__name__)


class AnalyticsClient:
    """Thin HTTP client for Analytics service endpoints used by Rasa actions."""

    def __init__(self, base_url: Optional[str] = None, *, timeout: float = 3.0) -> None:
        self._base_url = (base_url or settings.ANALYTICS_SERVICE_URL).rstrip("/")
        self._timeout = timeout
        self._unavailable_until: float = 0.0
        self._unavailable_cooldown_seconds: float = 5.0

    def _build_headers(self, token: Optional[str]) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if token:
            normalized = token.strip()
            if normalized and not normalized.lower().startswith("bearer "):
                normalized = f"Bearer {normalized}"
            if normalized:
                headers["Authorization"] = normalized
        return headers

    async def _get_json(self, endpoint: str, *, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        now = time.monotonic()
        if now < self._unavailable_until:
            LOGGER.warning(
                "[AnalyticsClient] skipping call to analytics service (cooldown active %.2fs): %s",
                self._unavailable_until - now,
                endpoint,
            )
            return None

        url = f"{self._base_url}{endpoint}"
        headers = self._build_headers(token)
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(url, headers=headers or None)
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPStatusError as exc:
                LOGGER.warning(
                    "[AnalyticsClient] %s returned %s on attempt %s: %s",
                    url,
                    exc.response.status_code,
                    attempt + 1,
                    exc,
                )
                if exc.response.status_code >= 500:
                    self._unavailable_until = time.monotonic() + self._unavailable_cooldown_seconds
                if exc.response.status_code >= 500 and attempt == 0:
                    await asyncio.sleep(0.5)
                    continue
            except httpx.RequestError as exc:
                LOGGER.warning(
                    "[AnalyticsClient] request failed for %s attempt %s: %s",
                    url,
                    attempt + 1,
                    exc,
                )
                self._unavailable_until = time.monotonic() + self._unavailable_cooldown_seconds
                if attempt == 0:
                    await asyncio.sleep(0.5)
                    continue
            except ValueError as exc:
                LOGGER.warning(
                    "[AnalyticsClient] invalid JSON for %s attempt %s: %s",
                    url,
                    attempt + 1,
                    exc,
                )
                if attempt == 0:
                    await asyncio.sleep(0.25)
                    continue
        return None

    async def get_campus_metrics(
        self,
        campus_id: int,
        *,
        token: Optional[str] = None,
        traffic_mode: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        endpoint = f"/analytics/campuses/{campus_id}/revenue-metrics"
        if traffic_mode:
            query = urlencode({"traffic_mode": traffic_mode})
            endpoint = f"{endpoint}?{query}"
        return await self._get_json(
            endpoint,
            token=token,
        )

    async def get_top_clients(
        self,
        campus_id: int,
        *,
        token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        return await self._get_json(
            f"/analytics/campuses/{campus_id}/top-clients",
            token=token,
        )

    async def get_top_fields(
        self,
        campus_id: int,
        *,
        token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        return await self._get_json(
            f"/analytics/campuses/{campus_id}/top-fields",
            token=token,
        )

    async def get_active_reservations(
        self,
        campus_id: int,
        *,
        token: Optional[str] = None,
        target_date: Optional[date] = None,
        field_name: Optional[str] = None,
        limit: int = 100,
    ) -> Optional[Dict[str, Any]]:
        params: Dict[str, str] = {"limit": str(limit)}
        if target_date is not None:
            params["target_date"] = target_date.isoformat()
        if field_name:
            params["field_name"] = field_name.strip()
        query = f"?{urlencode(params)}" if params else ""
        return await self._get_json(
            f"/analytics/campuses/{campus_id}/active-reservations{query}",
            token=token,
        )


analytics_client = AnalyticsClient()

__all__ = ["AnalyticsClient", "analytics_client"]
