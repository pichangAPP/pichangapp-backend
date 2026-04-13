"""Validacion de URLs publicas de imagenes (ej. Firebase Storage)."""
from __future__ import annotations

from urllib.parse import urlparse

from app.core.config import settings


def allowed_image_url_hosts() -> frozenset[str]:
    raw = (getattr(settings, "IMAGE_URL_ALLOWED_HOSTS", "") or "").strip()
    if raw:
        return frozenset(h.strip().lower() for h in raw.split(",") if h.strip())
    return frozenset(
        {
            "firebasestorage.googleapis.com",
            "pichangapp-storage.firebasestorage.app",
        }
    )


def validate_https_image_url(value: str) -> str:
    """Comprueba https y host permitido. Devuelve la URL normalizada."""
    url = (value or "").strip()
    if not url.startswith("https://"):
        raise ValueError("La URL de la imagen debe usar https")
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("URL de imagen invalida")
    allowed = allowed_image_url_hosts()
    if host not in allowed:
        raise ValueError(
            f"Dominio de imagen no permitido: {host}. "
            "Ajusta IMAGE_URL_ALLOWED_HOSTS en booking o usa Firebase Storage."
        )
    if len(url) > 4096:
        raise ValueError("URL de imagen demasiado larga")
    return url


def validate_image_url_in_mapping(data: dict[str, object]) -> None:
    """Si el dict trae image_url, valida formato (sync_campus/sync_field)."""
    if "image_url" not in data:
        return
    raw = data.get("image_url")
    if raw is None:
        return
    if not isinstance(raw, str):
        raise ValueError("image_url debe ser texto")
    validate_https_image_url(raw)


__all__ = [
    "allowed_image_url_hosts",
    "validate_https_image_url",
    "validate_image_url_in_mapping",
]
