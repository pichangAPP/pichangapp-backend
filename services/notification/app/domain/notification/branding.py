"""Marca y recursos visuales para correos y boletas."""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

_STATIC = Path(__file__).resolve().parent.parent.parent / "static"
_LOGO_PATH = _STATIC / "branding" / "cuadra_logo.png"


@lru_cache(maxsize=1)
def get_brand_logo_data_uri() -> str:
    """Data URI del logo para incrustar en HTML (evita adjuntos CID)."""
    if not _LOGO_PATH.is_file():
        return ""
    raw = _LOGO_PATH.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{b64}"


def get_brand_logo_path() -> Path:
    """Ruta al PNG del logo para la boleta generada con PIL."""
    return _LOGO_PATH


__all__ = ["get_brand_logo_data_uri", "get_brand_logo_path"]
