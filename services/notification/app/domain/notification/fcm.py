"""Envío FCM HTTP v1 vía firebase-admin."""

from __future__ import annotations

from firebase_admin import messaging

from app.core.config import settings
from app.core.firebase import get_firebase_app


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
    get_firebase_app()
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
    return messaging.send(msg)


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


__all__ = ["send_push", "is_unregistered_fcm_error"]
