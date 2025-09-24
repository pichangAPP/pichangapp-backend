from sqlalchemy import Column, BigInteger, String, Text, DateTime, ForeignKey, func

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "auth"}

    id_audit_log = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("auth.users.id_user"), nullable=False)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
