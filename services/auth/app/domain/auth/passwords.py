from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Hashea la contrasena en texto plano para persistirla de forma segura.

    Usado en: AuthService.register_user y AuthService.login_with_google
    (cuando se crea un usuario nuevo por login social).
    """
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica una contrasena contra su hash almacenado.

    Usado en: AuthService.login_user.
    """
    return _pwd_context.verify(plain_password, hashed_password)
