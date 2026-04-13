"""Firebase application initialization utilities for notification service."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import firebase_admin
from firebase_admin import credentials

from app.core.config import settings

logger = logging.getLogger(__name__)


def _build_init_kwargs() -> Dict[str, Any]:
    init_kwargs: Dict[str, Any] = {}
    if settings.FIREBASE_PROJECT_ID:
        init_kwargs["projectId"] = settings.FIREBASE_PROJECT_ID
    if settings.FIREBASE_STORAGE_BUCKET:
        init_kwargs["storageBucket"] = settings.FIREBASE_STORAGE_BUCKET
    return init_kwargs


def _resolve_credentials_path() -> Optional[str]:
    """Ruta al JSON de cuenta de servicio, o None si no se puede usar.

    Si Docker monta una ruta inexistente en el host, a veces aparece un
    directorio vacío con el nombre del archivo; Certificate() falla con EISDIR.
    """
    raw = (settings.FIREBASE_CREDENTIALS_PATH or "").strip()
    if not raw:
        return None
    if not os.path.isfile(raw):
        logger.warning(
            "FIREBASE_CREDENTIALS_PATH no apunta a un archivo JSON válido (%r). "
            "Comprueba el volumen en docker-compose y que el JSON exista en el host. "
            "Se intentará Application Default Credentials.",
            raw,
        )
        return None
    return raw


def get_firebase_app() -> firebase_admin.App:
    """Return the default Firebase app, initializing it if required."""

    if not firebase_admin._apps:  # type: ignore[attr-defined]
        cred_path = _resolve_credentials_path()
        if cred_path:
            cred = credentials.Certificate(cred_path)
        else:
            cred = credentials.ApplicationDefault()

        firebase_admin.initialize_app(cred, _build_init_kwargs())

    return firebase_admin.get_app()


__all__ = ["get_firebase_app"]
