from typing import List

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User
from app.repository import audit_log_repository, role_repository, user_repository


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def list_users(self, requester: User | None = None) -> List[User]:
        try:
            return user_repository.get_all_users(self.db)
        except SQLAlchemyError as exc:
            self.db.rollback()
            self._log_error(
                requester.id_user if requester else None,
                "list_users_error",
                f"Database error: {exc}",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve users",
            ) from exc
        except Exception as exc:  # pragma: no cover - defensive programming
            self.db.rollback()
            self._log_error(
                requester.id_user if requester else None,
                "list_users_unexpected_error",
                f"Unexpected error: {exc}",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unexpected error while retrieving users",
            ) from exc

    def list_active_users(self, requester: User | None = None) -> List[User]:
        try:
            return user_repository.get_users_by_status(self.db, "active")
        except SQLAlchemyError as exc:
            self.db.rollback()
            self._log_error(
                requester.id_user if requester else None,
                "list_active_users_error",
                f"Database error: {exc}",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve active users",
            ) from exc
        except Exception as exc:  # pragma: no cover - defensive programming
            self.db.rollback()
            self._log_error(
                requester.id_user if requester else None,
                "list_active_users_unexpected_error",
                f"Unexpected error: {exc}",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unexpected error while retrieving active users",
            ) from exc

    def list_users_by_role(self, role_id: int, requester: User | None = None) -> List[User]:
        role = role_repository.get_role_by_id(self.db, role_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found",
            )

        try:
            return user_repository.get_users_by_role(self.db, role_id)
        except SQLAlchemyError as exc:
            self.db.rollback()
            self._log_error(
                requester.id_user if requester else None,
                "list_users_by_role_error",
                f"Database error: {exc}",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve users by role",
            ) from exc
        except Exception as exc:  # pragma: no cover - defensive programming
            self.db.rollback()
            self._log_error(
                requester.id_user if requester else None,
                "list_users_by_role_unexpected_error",
                f"Unexpected error: {exc}",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unexpected error while retrieving users by role",
            ) from exc

    def _log_error(self, user_id: int | None, action: str, message: str) -> None:
        try:
            audit_entry = AuditLog(
                id_user=user_id,
                entity="UserService",
                action=action,
                message=message,
                state="error",
            )
            audit_log_repository.create_audit_log(self.db, audit_entry)
            self.db.commit()
        except Exception:
            self.db.rollback()
