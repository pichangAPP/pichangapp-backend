from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)

from app.core.database import Base


class StatusCatalog(Base):
    __tablename__ = "status_catalog"
    __table_args__ = (
        UniqueConstraint("entity", "code", name="uq_status_catalog"),
        {"schema": "reservation"},
    )

    id_status = Column(BigInteger, primary_key=True, index=True)
    entity = Column(String(20), nullable=False)
    code = Column(String(50), nullable=False)
    name = Column(String(80), nullable=False)
    description = Column(Text, nullable=False)
    is_final = Column(Boolean, nullable=False, server_default=text("false"))
    sort_order = Column(Integer, nullable=False, server_default=text("0"))
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
