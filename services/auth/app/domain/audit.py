from typing import Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.repository import audit_log_repository


def record_audit_log(
    db: Session,
    *,
    user_id: Optional[int],
    entity: str,
    action: str,
    message: str,
    state: str,
) -> AuditLog:
    """Registra un evento de auditoria sin forzar commit.

    Usado en: AuthService (register/login/google) y UserService.update_user.
    """
    audit_entry = AuditLog(
        id_user=user_id,
        entity=entity,
        action=action,
        message=message,
        state=state,
    )
    return audit_log_repository.create_audit_log(db, audit_entry)


def log_error(
    db: Session,
    *,
    user_id: Optional[int],
    entity: str,
    action: str,
    message: str,
) -> None:
    """Registra un error y hace commit inmediato para no perder el log.

    Usado en: UserService (errores en listados y consultas).
    """
    try:
        audit_entry = AuditLog(
            id_user=user_id,
            entity=entity,
            action=action,
            message=message,
            state="error",
        )
        audit_log_repository.create_audit_log(db, audit_entry)
        db.commit()
    except Exception:
        db.rollback()
