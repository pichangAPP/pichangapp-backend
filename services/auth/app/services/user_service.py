from typing import List, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.error_codes import (
    AUTH_INTERNAL_ERROR,
    http_error,
)
from app.models.user import User
from app.domain.audit import log_error, record_audit_log
from app.domain.user import get_role_or_error, get_user_or_error
from app.repository import user_repository


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def list_users(self, requester: User | None = None) -> List[User]:
        try:
            return user_repository.get_all_users(self.db)
        except SQLAlchemyError as exc:
            self.db.rollback()
            log_error(
                self.db,
                user_id=requester.id_user if requester else None,
                entity="UserService",
                action="list_users_error",
                message=f"Database error: {exc}",
            )
            raise http_error(
                AUTH_INTERNAL_ERROR,
                detail="Failed to retrieve users",
            ) from exc
        except Exception as exc:  # pragma: no cover - defensive programming
            self.db.rollback()
            log_error(
                self.db,
                user_id=requester.id_user if requester else None,
                entity="UserService",
                action="list_users_unexpected_error",
                message=f"Unexpected error: {exc}",
            )
            raise http_error(
                AUTH_INTERNAL_ERROR,
                detail="Unexpected error while retrieving users",
            ) from exc

    def list_active_users(self, requester: User | None = None) -> List[User]:
        try:
            return user_repository.get_users_by_status(self.db, "active")
        except SQLAlchemyError as exc:
            self.db.rollback()
            log_error(
                self.db,
                user_id=requester.id_user if requester else None,
                entity="UserService",
                action="list_active_users_error",
                message=f"Database error: {exc}",
            )
            raise http_error(
                AUTH_INTERNAL_ERROR,
                detail="Failed to retrieve active users",
            ) from exc
        except Exception as exc:  # pragma: no cover - defensive programming
            self.db.rollback()
            log_error(
                self.db,
                user_id=requester.id_user if requester else None,
                entity="UserService",
                action="list_active_users_unexpected_error",
                message=f"Unexpected error: {exc}",
            )
            raise http_error(
                AUTH_INTERNAL_ERROR,
                detail="Unexpected error while retrieving active users",
            ) from exc

    def list_users_by_role(self, role_id: int, requester: User | None = None) -> List[User]:
        get_role_or_error(self.db, role_id, detail="Role not found")

        try:
            return user_repository.get_users_by_role(self.db, role_id)
        except SQLAlchemyError as exc:
            self.db.rollback()
            log_error(
                self.db,
                user_id=requester.id_user if requester else None,
                entity="UserService",
                action="list_users_by_role_error",
                message=f"Database error: {exc}",
            )
            raise http_error(
                AUTH_INTERNAL_ERROR,
                detail="Failed to retrieve users by role",
            ) from exc
        except Exception as exc:  # pragma: no cover - defensive programming
            self.db.rollback()
            log_error(
                self.db,
                user_id=requester.id_user if requester else None,
                entity="UserService",
                action="list_users_by_role_unexpected_error",
                message=f"Unexpected error: {exc}",
            )
            raise http_error(
                AUTH_INTERNAL_ERROR,
                detail="Unexpected error while retrieving users by role",
            ) from exc

    def get_user_by_id(self, user_id: int, requester: User | None = None) -> Optional[User]:
        try:
            return get_user_or_error(self.db, user_id)
        except SQLAlchemyError as exc:
            self.db.rollback()
            log_error(
                self.db,
                user_id=requester.id_user if requester else None,
                entity="UserService",
                action="get_user_by_id_error",
                message=f"Database error: {exc}",
            )
            raise http_error(
                AUTH_INTERNAL_ERROR,
                detail="Failed to retrieve user by id",
            ) from exc
        except Exception as exc:
            self.db.rollback()
            log_error(
                self.db,
                user_id=requester.id_user if requester else None,
                entity="UserService",
                action="get_user_by_id_unexpected_error",
                message=f"Unexpected error: {exc}",
            )
            raise http_error(
                AUTH_INTERNAL_ERROR,
                detail="Unexpected error while retrieving user by id",
            ) from exc
       
        
    def exists_user_by_id(self, user_id: int) -> bool:
        return user_repository.exists_user_by_id(self.db, user_id)


    def update_user(self, user_id: int, updates: dict, requester: User | None = None) -> User:
        """
        Actualiza un usuario, excepto email y password_hash.
        updates puede contener: name, phone, status, id_role, etc.
        """
        try:
            user = get_user_or_error(self.db, user_id)

            # Validar rol
            get_role_or_error(
                self.db,
                updates["id_role"],
                detail=f"Role with id {updates['id_role']} not found",
            )

            # Actualizar solo campos permitidos
            user.name = updates["name"]
            user.lastname = updates["lastname"]
            user.phone = updates["phone"]
            user.imageurl = updates.get("imageurl", user.imageurl)
            user.birthdate = updates["birthdate"]
            user.gender = updates["gender"]
            user.city = updates["city"]
            user.district = updates["district"]
            user.status = updates["status"]
            user.id_role = updates["id_role"]

            self.db.flush()
            self.db.commit()
            self.db.refresh(user)

            # Log de auditoría
            record_audit_log(
                self.db,
                user_id=requester.id_user if requester else None,
                entity="UserService",
                action="update_user",
                message=f"User {user_id} updated",
                state="success",
            )
            self.db.commit()

            return user

        except SQLAlchemyError as exc:
            self.db.rollback()
            log_error(
                self.db,
                user_id=requester.id_user if requester else None,
                entity="UserService",
                action="update_user_error",
                message=f"Database error: {exc}",
            )
            raise http_error(
                AUTH_INTERNAL_ERROR,
                detail="Failed to update user",
            ) from exc
        except Exception as exc:
            self.db.rollback()
            log_error(
                self.db,
                user_id=requester.id_user if requester else None,
                entity="UserService",
                action="update_user_unexpected_error",
                message=f"Unexpected error: {exc}",
            )
            raise http_error(
                AUTH_INTERNAL_ERROR,
                detail="Unexpected error while updating user",
            ) from exc
