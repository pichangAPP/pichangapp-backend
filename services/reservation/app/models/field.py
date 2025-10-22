from sqlalchemy import BigInteger, Column, ForeignKey, Integer, Numeric, String, Text, Time

from app.core.database import Base


class Field(Base):

    __tablename__ = "field"
    __table_args__ = {"schema": "booking"}

    id_field = Column(BigInteger, primary_key=True, index=True)
    field_name = Column(String(200), nullable=False)
    capacity = Column(Integer, nullable=False)
    surface = Column(String(100), nullable=False)
    measurement = Column(Text, nullable=False)
    price_per_hour = Column(Numeric(10, 2), nullable=False)
    status = Column(String(100), nullable=False)
    open_time = Column(Time, nullable=False)
    close_time = Column(Time, nullable=False)
    minutes_wait = Column(Numeric(6, 2), nullable=False)
    id_sport = Column(Integer, ForeignKey("booking.sports.id_sport"), nullable=False)
    id_campus = Column(
        BigInteger,
        ForeignKey("booking.campus.id_campus", ondelete="CASCADE"),
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Field(id_field={self.id_field}, name={self.field_name})>"
