from sqlalchemy import BigInteger,Integer, Column

from app.core.database import Base


class Campus(Base):
    """Lightweight campus model providing metadata for foreign keys."""

    __tablename__ = "campus"
    __table_args__ = {"schema": "booking"}

    id_campus = Column(BigInteger, primary_key=True, index=True)

class Sport(Base):
    __tablename__ = "sports"
    __table_args__ = {"schema": "booking"}

    id_sport = Column(Integer, primary_key=True, index=True)

__all__ = ["Campus","Sport"]