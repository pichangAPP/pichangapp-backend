from sqlalchemy import BigInteger, Date, DateTime, Float, ForeignKey, Integer, String, Text,func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base, engine
class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = {"schema": "payment"}

    id_membership: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    membership_name: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)  # días, meses, etc.
    creation_date: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_payments: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)