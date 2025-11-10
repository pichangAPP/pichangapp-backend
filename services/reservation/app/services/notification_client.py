"""HTTP client for interacting with the notification microservice."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class NotificationClient:
    """Small wrapper around the notification API endpoints."""

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        configured_base = base_url or settings.NOTIFICATION_SERVICE_URL
        self._base_url = configured_base.rstrip("/") if configured_base else ""
        self._timeout = timeout or settings.NOTIFICATION_SERVICE_TIMEOUT

    @property
    def is_configured(self) -> bool:
        return bool(self._base_url)

    def send_rent_email(self, payload: Dict[str, Any]) -> None:
        if not self.is_configured:
            logger.info("Notification service URL not configured; skipping email dispatch")
            return

        url = f"{self._base_url}/api/pichangapp/v1/notification/notifications/send-email"

        try:
            response = httpx.post(url, json=payload, timeout=self._timeout)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:  # pragma: no cover - network dependent
            logger.warning(
                "Notification service returned HTTP %s while sending rent email: %s",
                exc.response.status_code,
                exc.response.text,
            )
        except httpx.RequestError as exc:  # pragma: no cover - network dependent
            logger.warning("Failed to reach notification service: %s", exc)


__all__ = ["NotificationClient"]
