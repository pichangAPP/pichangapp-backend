"""Firebase application initialization utilities."""

from __future__ import annotations

from typing import Any, Dict

import firebase_admin
from firebase_admin import credentials

from app.core.config import settings


def _build_init_kwargs() -> Dict[str, Any]:
    init_kwargs: Dict[str, Any] = {}
    if settings.FIREBASE_PROJECT_ID:
        init_kwargs["projectId"] = settings.FIREBASE_PROJECT_ID
    return init_kwargs


def get_firebase_app() -> firebase_admin.App:
    """Return the default Firebase app, initializing it if required."""

    if not firebase_admin._apps:  # type: ignore[attr-defined]
        if settings.FIREBASE_CREDENTIALS_PATH:
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        else:
            cred = credentials.ApplicationDefault()

        firebase_admin.initialize_app(cred, _build_init_kwargs())

    return firebase_admin.get_app()
