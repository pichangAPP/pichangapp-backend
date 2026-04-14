"""Registro de tokens push (auth.user_devices)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.dependencies import get_db
from app.repository.push_token_repository import deactivate_push_token, upsert_push_token
from app.schemas.push import PushTokenDelete, PushTokenRegister

router = APIRouter(prefix="/me", tags=["push"])


@router.put("/push-token", status_code=status.HTTP_204_NO_CONTENT)
def register_push_token(
    body: PushTokenRegister,
    id_user: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> None:
    upsert_push_token(
        db,
        id_user=id_user,
        push_token=body.token,
        platform=body.platform,
        device_name=body.device_name,
    )


@router.delete("/push-token", status_code=status.HTTP_204_NO_CONTENT)
def unregister_push_token(
    body: PushTokenDelete,
    id_user: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> None:
    deactivate_push_token(db, id_user=id_user, push_token=body.token)


__all__ = ["router"]
