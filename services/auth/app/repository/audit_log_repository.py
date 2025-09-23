from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def create_audit_log(db: Session, audit_log: AuditLog) -> AuditLog:
    db.add(audit_log)
    db.flush()
    return audit_log
