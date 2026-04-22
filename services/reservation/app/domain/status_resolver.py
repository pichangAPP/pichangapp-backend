"""Shared status resolution helpers for reservation services."""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repository import status_catalog_repository


def resolve_status_pair(
    db: Session,
    *,
    entity: str,
    status_code: Optional[str],
    status_id: Optional[int],
) -> tuple[str, int]:
    """Resolve the canonical status code/id pair for an entity.

    Used by: schedule and rent services when validating payload status fields.
    """
    if status_id is not None:
        status_item = status_catalog_repository.get_status(db, status_id)
        if status_item is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Status id {status_id} is not defined in status_catalog",
            )
        if status_code is not None and status_item.code != status_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Status id {status_id} does not match status {status_code!r}"
                ),
            )
        return status_item.code, int(status_item.id_status)

    if status_code is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="status or id_status must be provided",
        )

    return status_code, resolve_status_id(db, entity=entity, code=status_code)


def resolve_status_id(db: Session, *, entity: str, code: str) -> int:
    """Resolve a status id from a code (entity-agnostic).

    Used by: rent and schedule workflows when applying status transitions.
    """
    status_item = status_catalog_repository.get_status_by_code(
        db,
        code=code,
        is_active=True,
    )
    if status_item is not None:
        return int(status_item.id_status)

    # Fallback to any row by code (including inactive) for legacy catalogs.
    fallback_item = status_catalog_repository.get_status_by_code(
        db,
        code=code,
        is_active=None,
    )
    if fallback_item is not None:
        return int(fallback_item.id_status)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Status code {code!r} is not defined in status_catalog",
    )


__all__ = ["resolve_status_pair", "resolve_status_id"]
