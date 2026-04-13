from typing import Any, Dict

from firebase_admin import auth as firebase_auth

from app.core.error_codes import (
    EXPIRED_GOOGLE_TOKEN,
    INVALID_GOOGLE_TOKEN,
    REVOKED_GOOGLE_TOKEN,
    http_error,
)
from app.core.firebase import get_firebase_app


def verify_google_token(id_token: str) -> Dict[str, Any]:
    """Valida un id_token de Google y devuelve los claims decodificados.

    Usado en: AuthService.login_with_google.
    """
    get_firebase_app()

    try:
        return firebase_auth.verify_id_token(id_token)
    except firebase_auth.InvalidIdTokenError as exc:  # pragma: no cover - firebase specific
        raise http_error(
            INVALID_GOOGLE_TOKEN,
            detail="Invalid Google token",
        ) from exc
    except firebase_auth.ExpiredIdTokenError as exc:  # pragma: no cover
        raise http_error(
            EXPIRED_GOOGLE_TOKEN,
            detail="Expired Google token",
        ) from exc
    except firebase_auth.RevokedIdTokenError as exc:  # pragma: no cover
        raise http_error(
            REVOKED_GOOGLE_TOKEN,
            detail="Revoked Google token",
        ) from exc
    except Exception as exc:  # pragma: no cover - unexpected firebase errors
        raise http_error(
            INVALID_GOOGLE_TOKEN,
            detail="Could not validate Google token",
        ) from exc
