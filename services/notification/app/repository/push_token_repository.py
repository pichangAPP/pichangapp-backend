"""Persistencia de tokens FCM en auth.user_devices."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from app.models.user_device import UserDevice


def list_active_push_tokens(db: Session, id_user: int) -> List[str]:
    rows = (
        db.query(UserDevice.push_token)
        .filter(UserDevice.id_user == id_user, UserDevice.is_active.is_(True))
        .all()
    )
    return [r[0] for r in rows if r[0]]


def upsert_push_token(
    db: Session,
    *,
    id_user: int,
    push_token: str,
    platform: str,
    device_name: str | None,
) -> None:
    token = push_token.strip()
    row = db.query(UserDevice).filter(UserDevice.push_token == token).first()
    now = datetime.now(timezone.utc)
    if row:
        row.id_user = id_user
        row.platform = platform
        row.device_name = device_name
        row.is_active = True
        row.updated_at = now
    else:
        db.add(
            UserDevice(
                id_user=id_user,
                push_token=token,
                platform=platform,
                device_name=device_name,
                is_active=True,
            )
        )
    db.commit()


def deactivate_push_token(db: Session, *, id_user: int, push_token: str) -> int:
    """Desactiva el token si pertenece al usuario. Devuelve filas afectadas."""
    token = push_token.strip()
    q = (
        db.query(UserDevice)
        .filter(UserDevice.push_token == token, UserDevice.id_user == id_user)
        .all()
    )
    n = 0
    for row in q:
        row.is_active = False
        row.updated_at = datetime.now(timezone.utc)
        n += 1
    if n:
        db.commit()
    return n


def deactivate_token_globally(db: Session, push_token: str) -> None:
    """Marca inactivo un token (p. ej. FCM UNREGISTERED) sin filtrar por usuario."""
    token = push_token.strip()
    rows = db.query(UserDevice).filter(UserDevice.push_token == token).all()
    now = datetime.now(timezone.utc)
    for row in rows:
        row.is_active = False
        row.updated_at = now
    if rows:
        db.commit()


__all__ = [
    "list_active_push_tokens",
    "upsert_push_token",
    "deactivate_push_token",
    "deactivate_token_globally",
]
