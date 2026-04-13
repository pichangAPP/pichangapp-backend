from datetime import datetime, timedelta
from typing import Any, Dict

from jose import jwt

from app.core.config import settings


def build_role_claims(role_id: int) -> Dict[str, Any]:
    """Construye los claims relacionados al rol del usuario.

    Usado en: AuthService.register_user, AuthService.login_user,
    AuthService.login_with_google y AuthService.refresh_tokens.
    """
    return {"id_role": role_id}


def create_access_token(data: Dict[str, Any]) -> str:
    """Genera un JWT de acceso con expiracion corta.

    Usado en: AuthService.register_user, AuthService.login_user,
    AuthService.login_with_google y AuthService.refresh_tokens.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Genera un JWT de refresco con expiracion mas larga.

    Usado en: AuthService.register_user, AuthService.login_user,
    AuthService.login_with_google y AuthService.refresh_tokens.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
