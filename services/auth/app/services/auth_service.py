import secrets
from typing import Tuple

from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.error_codes import (
    AUTH_INTERNAL_ERROR,
    DEFAULT_ROLE_NOT_CONFIGURED,
    EMAIL_ALREADY_REGISTERED,
    GOOGLE_EMAIL_MISSING,
    INVALID_CREDENTIALS,
    INVALID_GOOGLE_TOKEN,
    INVALID_REFRESH_TOKEN,
    http_error,
)
from app.models.user import User
from app.domain.audit import record_audit_log
from app.domain.auth import (
    build_role_claims,
    create_access_token,
    create_refresh_token,
    create_user_session,
    hash_password,
    verify_google_token,
    verify_password,
)
from app.domain.user import get_role_or_error, get_user_or_error
from app.repository import role_repository, user_repository
from app.schemas.auth import LoginRequest, RegisterRequest


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def register_user(self, register_data: RegisterRequest) -> Tuple[str, str, User]:
        existing_user = user_repository.get_user_by_email(self.db, register_data.email)
        if existing_user:
            raise http_error(
                EMAIL_ALREADY_REGISTERED,
                detail="Email already registered",
            )

        get_role_or_error(self.db, register_data.id_role, detail="Role not found")

        hashed_password = hash_password(register_data.password)

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
            record_audit_log(
                self.db,
                user_id=None,
                entity="AuthService",
                action="register_error",
                message="User creation failed: repository returned null",
                state="error",
            )

            raise http_error(
                AUTH_INTERNAL_ERROR,
                detail="User could not be created",
            )

        record_audit_log(
            self.db,
            user_id=new_user.id_user,
            entity="AuthService",
            action="register",
            message="User registered",
            state="active",
        )

        token_claims = {
            "sub": str(new_user.id_user),
            "email": new_user.email,
            "id_user": new_user.id_user,
            **build_role_claims(new_user.id_role),
        }

        access_token = create_access_token(token_claims)

        refresh_token = create_refresh_token(token_claims)

        create_user_session(self.db, new_user.id_user, access_token, refresh_token)

        try:
            self.db.commit()
        except Exception as exc:
            self.db.rollback()

            record_audit_log(
                self.db,
                user_id=None,
                entity="AuthService",
                action="register_exception",
                message=f"Exception during commit: {str(exc)}",
                state="active",
            )

            raise http_error(
                AUTH_INTERNAL_ERROR,
                detail="Unexpected error while saving user",
            ) from exc

        self.db.refresh(new_user)

        return access_token, refresh_token, new_user

    def login_user(self, login_data: LoginRequest) -> Tuple[str, str, User]:
        user = user_repository.get_user_by_email(self.db, login_data.email)
        if not user or not verify_password(login_data.password, user.password_hash):
            raise http_error(
                INVALID_CREDENTIALS,
                detail="Invalid email or password",
            )

        token_claims = {
            "sub": str(user.id_user),
            "email": user.email,
            "id_user": user.id_user,
            **build_role_claims(user.id_role),
        }

        access_token = create_access_token(token_claims)
        refresh_token = create_refresh_token(token_claims)

        record_audit_log(
            self.db,
            user_id=user.id_user,
            entity="AuthService",
            action="login",
            message="User login",
            state="active",
        )

        create_user_session(self.db, user.id_user, access_token, refresh_token)

        try:
            self.db.commit()
        except Exception as exc:

            self.db.rollback()
            record_audit_log(
                self.db,
                user_id=None,
                entity="AuthService",
                action="login_exception",
                message=f"Exception during commit: {str(exc)}",
                state="active",
            )
            raise http_error(
                AUTH_INTERNAL_ERROR,
                detail="Could not complete login",
            ) from exc

        return access_token, refresh_token, user

    def login_with_google(self, id_token: str) -> Tuple[str, str, User]:
        # Validate the external token first; we short-circuit before touching the DB to avoid
        # persisting sessions for unverified identities.
        decoded_token = verify_google_token(id_token)

        email = decoded_token.get("email")
        if not email:
            raise http_error(
                GOOGLE_EMAIL_MISSING,
                detail="Google token does not contain an email",
            )

        if decoded_token.get("email_verified") is not True:
            raise http_error(
                INVALID_GOOGLE_TOKEN,
                detail="Google account email is not verified",
            )

        provider = (decoded_token.get("firebase") or {}).get("sign_in_provider")
        if provider != "google.com":
            raise http_error(
                INVALID_GOOGLE_TOKEN,
                detail="Token sign-in provider is not Google",
            )

        user = user_repository.get_user_by_email(self.db, email)

        if not user:
            name = decoded_token.get("name") or "Google User"
            name_parts = name.split(" ", 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else "Google"

            random_password = hash_password(secrets.token_urlsafe(32))

            user = User(
                name=first_name,
                lastname=last_name,
                email=email,
                imageurl=decoded_token.get("picture") or None,
                phone=decoded_token.get("phone_number") or "000000000",
                birthdate=None,
                # auth.users.gender is VARCHAR(10) in DB.
                gender="other",
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
                raise http_error(
                    DEFAULT_ROLE_NOT_CONFIGURED,
                    detail="Default role for social login not configured",
                )

            user_repository.create_user(self.db, user)

            record_audit_log(
                self.db,
                user_id=user.id_user,
                entity="AuthService",
                action="google_register",
                message="User registered via Google",
                state="active",
            )

        token_claims = {
            "sub": str(user.id_user),
            "email": user.email,
            "id_user": user.id_user,
            **build_role_claims(user.id_role),
        }

        access_token = create_access_token(token_claims)
        refresh_token = create_refresh_token(token_claims)

        record_audit_log(
            self.db,
            user_id=user.id_user,
            entity="AuthService",
            action="google_login",
            message="User login with Google",
            state="active",
        )

        create_user_session(self.db, user.id_user, access_token, refresh_token)

        try:
            self.db.commit()
        except Exception as exc:  #  database errors
            self.db.rollback()
            raise http_error(
                AUTH_INTERNAL_ERROR,
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
            raise http_error(
                INVALID_REFRESH_TOKEN,
                detail="Invalid refresh token",
            ) from exc

        if payload.get("type") != "refresh":
            raise http_error(
                INVALID_REFRESH_TOKEN,
                detail="Invalid refresh token",
            )

        user_id = payload.get("sub")
        if not user_id:
            raise http_error(
                INVALID_REFRESH_TOKEN,
                detail="Invalid refresh token",
            )

        user = get_user_or_error(self.db, int(user_id), detail="User not found")

        token_claims = {
            "sub": str(user.id_user),
            "email": user.email,
            "id_user": user.id_user,
            **build_role_claims(user.id_role),
        }

        access_token = create_access_token(token_claims)
        new_refresh_token = create_refresh_token(token_claims)

        return access_token, new_refresh_token, user
