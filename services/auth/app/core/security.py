from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.dependencies import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.repository import audit_log_repository, user_repository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        user_id = payload.get("sub")
    except JWTError as exc:
        _log_security_event(db, "token_decode_error", f"Invalid token: {exc}")
        raise credentials_exception from exc

    if user_id is None:
        _log_security_event(db, "token_missing_sub", "Token payload missing subject")
        raise credentials_exception

    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError) as exc:
        _log_security_event(db, "token_invalid_sub", f"Invalid subject: {user_id}")
        raise credentials_exception from exc

    user = user_repository.get_user_by_id(db, user_id_int)
    if not user:
        _log_security_event(db, "user_not_found", f"User id {user_id_int} not found")
        raise credentials_exception

    return user


def _log_security_event(db: Session, action: str, message: str) -> None:
    try:
        audit_entry = AuditLog(
            id_user=None,
            entity="Security",
            action=action,
            message=message,
            state="error",
        )
        audit_log_repository.create_audit_log(db, audit_entry)
        db.commit()
    except Exception:
        db.rollback()
