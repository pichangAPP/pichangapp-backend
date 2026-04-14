"""Envío FCM HTTP v1 vía firebase-admin."""

from __future__ import annotations

import logging
import os

import firebase_admin
from firebase_admin import credentials
from firebase_admin import messaging

from app.core.config import settings

logger = logging.getLogger(__name__)
_FCM_APP_NAME = "notification-fcm"


def _resolve_fcm_credentials_path() -> str | None:
    raw = (settings.FCM_FIREBASE_CREDENTIALS_PATH or "").strip()
    if not raw:
        return None
    if not os.path.isfile(raw):
        logger.warning(
            "FCM_FIREBASE_CREDENTIALS_PATH no apunta a un archivo JSON válido (%r). "
            "Se intentará Application Default Credentials.",
            raw,
        )
        return None
    return raw


def get_fcm_firebase_app() -> firebase_admin.App:
    try:
        return firebase_admin.get_app(_FCM_APP_NAME)
    except ValueError:
        cred_path = _resolve_fcm_credentials_path()
        if cred_path:
            cred = credentials.Certificate(cred_path)
        else:
            cred = credentials.ApplicationDefault()

        options: dict[str, str] = {}
        if settings.FCM_FIREBASE_PROJECT_ID:
            options["projectId"] = settings.FCM_FIREBASE_PROJECT_ID
        return firebase_admin.initialize_app(cred, options=options, name=_FCM_APP_NAME)


def _android_config() -> messaging.AndroidConfig:
    ch = settings.FCM_ANDROID_NOTIFICATION_CHANNEL_ID
    if ch:
        return messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(channel_id=ch),
        )
    return messaging.AndroidConfig(priority="high")


def send_push(
    fcm_token: str,
    title: str,
    body: str,
    data: dict[str, str],
) -> str:
    """Envía un mensaje a un token. Devuelve message_id."""
    app = get_fcm_firebase_app()
    msg = messaging.Message(
        token=fcm_token.strip(),
        notification=messaging.Notification(title=title, body=body),
        data={k: str(v) for k, v in data.items()},
        android=_android_config(),
        apns=messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(sound="default"),
            ),
        ),
    )
    return messaging.send(msg, app=app)


def is_unregistered_fcm_error(exc: BaseException) -> bool:
    """True si el error indica token inválido / desinstalado."""
    unreg = getattr(messaging, "UnregisteredError", None)
    mismatch = getattr(messaging, "SenderIdMismatchError", None)
    if unreg and isinstance(exc, unreg):
        return True
    if mismatch and isinstance(exc, mismatch):
        return True
    text = str(exc).lower()
    return "unregistered" in text or "registration-token-not-registered" in text


__all__ = ["send_push", "is_unregistered_fcm_error", "get_fcm_firebase_app"]
