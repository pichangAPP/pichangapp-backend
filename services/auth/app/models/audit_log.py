from sqlalchemy import Column, BigInteger, String, Text, DateTime, ForeignKey, func

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "auth"}

    id_log = Column(BigInteger, primary_key=True, index=True)
    entity = Column(String(100), nullable=False)
    action = Column(Text, nullable=False)
    message = Column(Text, nullable=False)
    state = Column(String(30), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    id_user = Column(BigInteger, ForeignKey("auth.users.id_user"), nullable=False)
