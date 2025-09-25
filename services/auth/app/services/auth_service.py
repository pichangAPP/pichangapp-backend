from datetime import datetime, timedelta
from typing import Dict, Tuple

from fastapi import HTTPException, status
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.user import User
from app.repository import audit_log_repository, role_repository, user_repository
from app.schemas.auth import LoginRequest, RegisterRequest

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def register_user(self, register_data: RegisterRequest) -> Tuple[str, User]:
        existing_user = user_repository.get_user_by_email(self.db, register_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        role = role_repository.get_role_by_id(self.db, register_data.id_role)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found",
            )

        hashed_password = _pwd_context.hash(register_data.password)

        new_user = User(
            name=register_data.name,
            email=register_data.email,
            phone=register_data.phone,
            password_hash=hashed_password,
            id_role=register_data.id_role,
            status="active",
        )

        user_db = user_repository.create_user(self.db, new_user)
        
        if not user_db or not user_db.id_user:
            audit_entry = AuditLog(
                user_id=None,
                action="register_error",
                message="User creation failed: repository returned null"
            )
            audit_log_repository.create_audit_log(self.db, audit_entry)

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User could not be created"
            )

        audit_entry = AuditLog(
            user_id=new_user.id_user,
            action="register",
            message="User registered",
        )

        audit_log_repository.create_audit_log(self.db, audit_entry)

        try:
            self.db.commit()
        except Exception as exc:
            self.db.rollback()

            audit_entry = AuditLog(
                user_id=None,
                action="register_exception",
                message=f"Exception during commit: {str(exc)}"
            )
            audit_log_repository.create_audit_log(self.db, audit_entry)

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unexpected error while saving user"
            ) from exc

        self.db.refresh(new_user)
        access_token = self._create_access_token({"sub": str(new_user.id_user), "email": new_user.email})

        return access_token,new_user

    def login_user(self, login_data: LoginRequest) -> Tuple[str, User]:
        user = user_repository.get_user_by_email(self.db, login_data.email)
        if not user or not _pwd_context.verify(login_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        access_token = self._create_access_token({"sub": str(user.id_user), "email": user.email})

        audit_entry = AuditLog(
            user_id=user.id_user,
            action="login",
            message="User login",
        )
        audit_log_repository.create_audit_log(self.db, audit_entry)

        try:
            self.db.commit()
        except Exception as exc:  # pragma: no cover - defensive rollback
            self.db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not complete login") from exc

        return access_token, user

    def _create_access_token(self, data: Dict[str, str]) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
