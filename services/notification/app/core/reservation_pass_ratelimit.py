"""Límite simple por IP para GET /reservation-pass (mitiga abuso de ancho de banda)."""
from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from app.core.config import settings

_lock = Lock()
_by_ip: dict[str, list[float]] = defaultdict(list)
_business_request_by_ip: dict[str, list[float]] = defaultdict(list)


def _client_ip(forwarded: str | None, direct: str | None) -> str:
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    return (direct or "").strip() or "unknown"


def reservation_pass_rate_limit_exceeded(client_ip: str) -> bool:
    """True si la IP superó el cupo en la ventana de un minuto."""
    limit = max(5, int(getattr(settings, "RESERVATION_PASS_RATE_LIMIT_PER_MINUTE", 40)))
    window = 60.0
    now = time.time()
    cutoff = now - window
    with _lock:
        hits = _by_ip[client_ip]
        hits[:] = [t for t in hits if t > cutoff]
        if len(hits) >= limit:
            return True
        hits.append(now)
    return False


def business_request_rate_limit_exceeded(client_ip: str) -> bool:
    """True si la IP supero el cupo de solicitudes de negocio por minuto."""
    limit = 10
    window = 60.0
    now = time.time()
    cutoff = now - window
    with _lock:
        hits = _business_request_by_ip[client_ip]
        hits[:] = [t for t in hits if t > cutoff]
        if len(hits) >= limit:
            return True
        hits.append(now)
    return False


def client_ip_from_request(forwarded: str | None, direct: str | None) -> str:
    return _client_ip(forwarded, direct)


__all__ = [
    "client_ip_from_request",
    "reservation_pass_rate_limit_exceeded",
    "business_request_rate_limit_exceeded",
]
