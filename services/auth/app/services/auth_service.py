from datetime import datetime, timedelta, timezone
import secrets
from typing import Any, Dict, Tuple

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.firebase import get_firebase_app
from app.models.audit_log import AuditLog
from app.models.session import UserSession
from app.models.user import User
from app.repository import audit_log_repository, role_repository, session_repository, user_repository
from app.schemas.auth import LoginRequest, RegisterRequest

from firebase_admin import auth as firebase_auth

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def register_user(self, register_data: RegisterRequest) -> Tuple[str, str, User]:
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
            lastname=register_data.lastname,
            email=register_data.email,
            phone=register_data.phone,
            imageurl=register_data.imageurl,
            birthdate=register_data.birthdate,
            gender=register_data.gender,
            city=register_data.city,
            district=register_data.district,
            password_hash=hashed_password,
            id_role=register_data.id_role,
            status="active",
        )

        user_db = user_repository.create_user(self.db, new_user)
        
        if not user_db or not user_db.id_user:
            audit_entry = AuditLog(
                id_user=None,
                entity="AuthService",
                action="register_error",
                message="User creation failed: repository returned null"
            )
            audit_log_repository.create_audit_log(self.db, audit_entry)

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User could not be created"
            )

        audit_entry = AuditLog(
            id_user=new_user.id_user,
            entity="AuthService",
            action="register",
            message="User registered",
            state="active"
        )

        audit_log_repository.create_audit_log(self.db, audit_entry)

        token_claims = {
            "sub": str(new_user.id_user),
            "email": new_user.email,
            "id_user": new_user.id_user,
            **self._build_role_claims(new_user.id_role),
        }

        access_token = self._create_access_token(token_claims)

        refresh_token = self._create_refresh_token(token_claims)

        self._create_user_session(new_user.id_user, access_token, refresh_token)

        try:
            self.db.commit()
        except Exception as exc:
            self.db.rollback()

            audit_entry = AuditLog(
                id_user=None,
                entity="AuthService",
                action="register_exception",
                message=f"Exception during commit: {str(exc)}",
                state="active"
            )
            audit_log_repository.create_audit_log(self.db, audit_entry)

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unexpected error while saving user"
            ) from exc

        self.db.refresh(new_user)

        return access_token, refresh_token, new_user

    def login_user(self, login_data: LoginRequest) -> Tuple[str, str, User]:
        user = user_repository.get_user_by_email(self.db, login_data.email)
        if not user or not _pwd_context.verify(login_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        token_claims = {
            "sub": str(user.id_user),
            "email": user.email,
            "id_user": user.id_user,
            **self._build_role_claims(user.id_role),
        }

        access_token = self._create_access_token(token_claims)
        refresh_token = self._create_refresh_token(token_claims)

        audit_entry = AuditLog(
            id_user=user.id_user,
            entity="AuthService",
            action="login",
            message="User login",
            state="active"
        )
        audit_log_repository.create_audit_log(self.db, audit_entry)

        self._create_user_session(user.id_user, access_token, refresh_token)

        try:
            self.db.commit()
        except Exception as exc:

            self.db.rollback()
            audit_entry = AuditLog(
                id_user=None,
                entity="AuthService",
                action="login_exception",
                message=f"Exception during commit: {str(exc)}",
                state="active"
            )
            audit_log_repository.create_audit_log(self.db, audit_entry)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not complete login"
            ) from exc

        return access_token, refresh_token, user

    def login_with_google(self, id_token: str) -> Tuple[str, str, User]:
        get_firebase_app()

        # Validate the external token first; we short-circuit before touching the DB to avoid
        # persisting sessions for unverified identities.
        try:
            decoded_token = firebase_auth.verify_id_token(id_token)
        except firebase_auth.InvalidIdTokenError as exc:  # pragma: no cover - firebase specific
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google token",
            ) from exc
        except firebase_auth.ExpiredIdTokenError as exc:  # pragma: no cover
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Expired Google token",
            ) from exc
        except firebase_auth.RevokedIdTokenError as exc:  # pragma: no cover
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Revoked Google token",
            ) from exc
        except Exception as exc:  # pragma: no cover - unexpected firebase errors
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate Google token",
            ) from exc

        email = decoded_token.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google token does not contain an email",
            )

        user = user_repository.get_user_by_email(self.db, email)

        if not user:
            name = decoded_token.get("name") or "Google User"
            name_parts = name.split(" ", 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else "Google"

            random_password = _pwd_context.hash(secrets.token_urlsafe(32))

            user = User(
                name=first_name,
            lastname=last_name,
            email=email,
                imageurl=decoded_token.get("picture") or None,
                phone=decoded_token.get("phone_number") or "000000000",
                birthdate=None,
                gender="unspecified",
                city=None,
                district=None,
            password_hash=random_password,
            id_role=settings.DEFAULT_SOCIAL_ROLE_ID,
            status="active",
        )

            # On first login we provision the user locally with the default social role so later
            # requests can reuse the same auth flow without duplicating rows.
            role = role_repository.get_role_by_id(self.db, user.id_role)
            if not role:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Default role for social login not configured",
                )

            user_repository.create_user(self.db, user)

            audit_entry = AuditLog(
                id_user=user.id_user,
                entity="AuthService",
                action="google_register",
                message="User registered via Google",
                state="active",
            )
            audit_log_repository.create_audit_log(self.db, audit_entry)

        token_claims = {
            "sub": str(user.id_user),
            "email": user.email,
            "id_user": user.id_user,
            **self._build_role_claims(user.id_role),
        }

        access_token = self._create_access_token(token_claims)
        refresh_token = self._create_refresh_token(token_claims)

        audit_entry = AuditLog(
            id_user=user.id_user,
            entity="AuthService",
            action="google_login",
            message="User login with Google",
            state="active",
        )
        audit_log_repository.create_audit_log(self.db, audit_entry)

        self._create_user_session(user.id_user, access_token, refresh_token)

        try:
            self.db.commit()
        except Exception as exc:  #  database errors
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not complete Google login",
            ) from exc

        self.db.refresh(user)

        return access_token, refresh_token, user

    def refresh_tokens(self, refresh_token: str) -> Tuple[str, str, User]:
        try:
            payload = jwt.decode(
                refresh_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
        except JWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            ) from exc

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        user = user_repository.get_user_by_id(self.db, int(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        token_claims = {
            "sub": str(user.id_user),
            "email": user.email,
            "id_user": user.id_user,
            **self._build_role_claims(user.id_role),
        }

        access_token = self._create_access_token(token_claims)
        new_refresh_token = self._create_refresh_token(token_claims)

        return access_token, new_refresh_token, user

    @staticmethod
    def _build_role_claims(role_id: int) -> Dict[str, Any]:
        return {"id_role": role_id}

    def _create_access_token(self, data: Dict[str, Any]) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire, "type": "access"})
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    def _create_refresh_token(self, data: Dict[str, Any]) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire, "type": "refresh"})
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    def _create_user_session(
        self, user_id: int, access_token: str, refresh_token: str
    ) -> UserSession:
        session_repository.delete_sessions_by_user(self.db, user_id)

        expires_at = None
        if settings.REFRESH_TOKEN_EXPIRE_MINUTES:
            expires_at = datetime.now(timezone.utc) + timedelta(
                minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
            )

        user_session = UserSession(
            id_user=user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            is_active=True,
        )

        return session_repository.create_session(self.db, user_session)
