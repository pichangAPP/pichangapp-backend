"""Helpers de texto compartidos por el dominio del chatbot."""

from __future__ import annotations

import unicodedata
from typing import Optional


def normalize_plain_text(text: Optional[str]) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFD", text)
    normalized = normalized.encode("ascii", "ignore").decode("utf-8")
    return normalized.lower()
