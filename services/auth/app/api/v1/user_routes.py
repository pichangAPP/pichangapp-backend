from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.dependencies import get_db
from app.models.user import User
from app.schemas.auth import UserResponse, UserUpdateRequest
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

@router.get("/{user_id}", response_model=UserResponse)
def get_user_by_id(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_service = UserService(db)
    return user_service.get_user_by_id(user_id, current_user)

@router.get("/{user_id}/exists", response_model=bool)
def check_user_exists(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_service = UserService(db)
    return user_service.exists_user_by_id(user_id)

@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    updates: UserUpdateRequest,  # 👈 Validamos lo que se puede actualizar
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_service = UserService(db)
    return user_service.update_user(user_id, updates.dict(exclude_unset=True), current_user)