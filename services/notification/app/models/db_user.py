"""Minimal mapping to auth.users for JWT validation."""

from sqlalchemy import BigInteger, Column

from app.core.database import Base


class DbUser(Base):
    """Solo id_user: suficiente para comprobar que el sujeto del JWT existe."""

    __tablename__ = "users"
    __table_args__ = {"schema": "auth"}

    id_user = Column(BigInteger, primary_key=True, index=True)
