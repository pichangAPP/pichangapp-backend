from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.dependencies import get_db
from app.models.user import User
from app.schemas.auth import UserResponse
from app.services.user_service import UserService

router = APIRouter()


@router.get("/", response_model=List[UserResponse])
def get_users(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    user_service = UserService(db)
    return user_service.list_users(current_user)


@router.get("/active", response_model=List[UserResponse])
def get_active_users(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    user_service = UserService(db)
    return user_service.list_active_users(current_user)


@router.get("/roles/{role_id}", response_model=List[UserResponse])
def get_users_by_role(
    role_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_service = UserService(db)
    return user_service.list_users_by_role(role_id, current_user)
