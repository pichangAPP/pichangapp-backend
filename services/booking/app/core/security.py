from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import settings
from app.core.error_codes import AUTH_INVALID_CREDENTIALS, AUTH_NOT_AUTHENTICATED, http_error

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """Validate the bearer token issued by the Auth service.

    Returns the decoded JWT payload to downstream dependencies. Raises an HTTP 401
    error when the token is missing or invalid.
    """

    if credentials is None or not credentials.scheme or credentials.scheme.lower() != "bearer":
        exc = http_error(
            AUTH_NOT_AUTHENTICATED,
            detail="Not authenticated",
        )
        exc.headers = {"WWW-Authenticate": "Bearer"}
        raise exc

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except JWTError as exc:
        auth_exc = http_error(
            AUTH_INVALID_CREDENTIALS,
            detail="Could not validate credentials",
        )
        auth_exc.headers = {"WWW-Authenticate": "Bearer"}
        raise auth_exc from exc

    return payload


__all__ = ["get_current_user"]
