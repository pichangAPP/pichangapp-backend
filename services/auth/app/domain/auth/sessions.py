from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.session import UserSession
from app.repository import session_repository


def create_user_session(
    db: Session, user_id: int, access_token: str, refresh_token: str
) -> UserSession:
    """Regenera la sesion activa del usuario y persiste los nuevos tokens.

    Usado en: AuthService.register_user, AuthService.login_user y
    AuthService.login_with_google.
    """
    session_repository.delete_sessions_by_user(db, user_id)

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

    return session_repository.create_session(db, user_session)
