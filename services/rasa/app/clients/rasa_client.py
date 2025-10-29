"""Async client helper for talking to the Rasa server."""

from __future__ import annotations

from typing import Any, Dict, List

import httpx


class RasaClient:
    """Utility to forward messages to a running Rasa server."""

    def __init__(self, base_url: str, *, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def send_message(
        self,
        sender_id: str,
        message: str,
        metadata: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        endpoint = f"{self._base_url}/webhooks/rest/webhook"
        payload = {
            "sender": sender_id,
            "message": message,
            "metadata": metadata,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(endpoint, json=payload)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                return data
            return [data]


__all__ = ["RasaClient"]
