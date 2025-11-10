"""ORM model that exposes booking campus information to the reservation service."""

from sqlalchemy import BigInteger, Column, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.user import User


class Campus(Base):
    __tablename__ = "campus"
    __table_args__ = {"schema": "booking"}

    id_campus = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    address = Column(Text, nullable=False)
    district = Column(String(200), nullable=False)
    id_manager = Column(BigInteger, ForeignKey("auth.users.id_user"), nullable=True)

    manager = relationship(User, lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Campus(id_campus={self.id_campus}, name={self.name})>"


__all__ = ["Campus"]
