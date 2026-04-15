"""Firebase application initialization utilities."""

from __future__ import annotations

from typing import Any, Dict

import firebase_admin
from firebase_admin import credentials

from app.core.config import settings


def _build_init_kwargs() -> Dict[str, Any]:
    init_kwargs: Dict[str, Any] = {}
    pid = settings.FCM_FIREBASE_PROJECT_ID.strip()
    if pid:
        init_kwargs["projectId"] = pid
    return init_kwargs


def get_firebase_app() -> firebase_admin.App:
    """Return the default Firebase app, initializing it if required."""

    if not firebase_admin._apps:  # type: ignore[attr-defined]
        cred_path = settings.FCM_FIREBASE_CREDENTIALS_PATH.strip()
        if cred_path:
            cred = credentials.Certificate(cred_path)
        else:
            cred = credentials.ApplicationDefault()

        firebase_admin.initialize_app(cred, _build_init_kwargs())

    return firebase_admin.get_app()
