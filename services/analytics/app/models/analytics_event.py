"""SQLAlchemy model for the analytics.analytics table."""

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Identity, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class AnalyticsEvent(Base):
    """Stores detailed analytics events linked to KPI calculations."""

    __tablename__ = "analytics"
    __table_args__ = {"schema": "analytics"}

    id_analytics = Column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
        index=True,
    )
    action = Column(Text, nullable=False)
    metadata = Column(JSONB, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    id_rent = Column(
        BigInteger,
        ForeignKey("reservation.rent.id_rent"),
        nullable=False,
    )
    id_kpi = Column(
        BigInteger,
        ForeignKey("analytics.kpi_log.id_kpi"),
        nullable=False,
    )

    kpi = relationship("KpiLog", back_populates="analytics_events")


__all__ = ["AnalyticsEvent"]
