from typing import Optional

from sqlalchemy.orm import Session

from app.core.error_codes import ROLE_NOT_FOUND, USER_NOT_FOUND, http_error
from app.models.role import Role
from app.models.user import User
from app.repository import role_repository, user_repository


def get_user_or_error(db: Session, user_id: int, detail: Optional[str] = None) -> User:
    """Obtiene un usuario por id o lanza un error controlado.

    Usado en: UserService.get_user_by_id y AuthService.refresh_tokens.
    """
    user = user_repository.get_user_by_id(db, user_id)
    if not user:
        raise http_error(
            USER_NOT_FOUND,
            detail=detail or f"User with id {user_id} not found",
        )
    return user


def get_role_or_error(db: Session, role_id: int, detail: Optional[str] = None) -> Role:
    """Obtiene un rol por id o lanza un error controlado.

    Usado en: AuthService.register_user y UserService.list_users_by_role / update_user.
    """
    role = role_repository.get_role_by_id(db, role_id)
    if not role:
        raise http_error(
            ROLE_NOT_FOUND,
            detail=detail or "Role not found",
        )
    return role
