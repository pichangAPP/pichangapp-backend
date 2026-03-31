"""Internal auth API for service-to-service lookups."""

from __future__ import annotations

from typing import List, Optional
import secrets

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.error_codes import (
    INTERNAL_API_KEY_MISSING,
    INVALID_INTERNAL_CREDENTIALS,
    USER_NOT_FOUND,
    http_error,
)
from app.dependencies import get_db
from app.repository import user_repository
from app.schemas.auth import UserResponse

router = APIRouter(prefix="/internal", tags=["internal"])


def _require_internal_key(
    x_internal_auth: Optional[str] = Header(default=None, alias="X-Internal-Auth"),
) -> None:
    expected = settings.AUTH_INTERNAL_API_KEY
    if not expected:
        raise http_error(
            INTERNAL_API_KEY_MISSING,
            detail="Internal API key not configured",
        )
    if x_internal_auth is None or not secrets.compare_digest(x_internal_auth, expected):
        raise http_error(
            INVALID_INTERNAL_CREDENTIALS,
            detail="Invalid internal credentials",
        )


@router.get(
    "/users/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(_require_internal_key)],
)
def get_internal_user(
    user_id: int,
    db: Session = Depends(get_db),
) -> UserResponse:
    user = user_repository.get_user_by_id(db, user_id)
    if user is None:
        raise http_error(
            USER_NOT_FOUND,
            detail="User not found",
        )
    return user


@router.get(
    "/users",
    response_model=List[UserResponse],
    dependencies=[Depends(_require_internal_key)],
)
def get_internal_users(
    ids: List[int] = Query(default_factory=list, alias="ids"),
    db: Session = Depends(get_db),
) -> List[UserResponse]:
    if not ids:
        return []
    users = user_repository.get_users_by_ids(db, ids)
    return users


__all__ = ["router"]
