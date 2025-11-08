"""SQLAlchemy model for the analytics.kpi_log table."""

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class KpiLog(Base):
    """Represents a record of a KPI calculation."""

    __tablename__ = "kpi_log"
    __table_args__ = {"schema": "analytics"}

    id_kpi = Column(BigInteger, primary_key=True, index=True)
    kpi_name = Column(String(300), nullable=False)
    metric_value = Column(Numeric(10, 2), nullable=False)
    period = Column(String(30), nullable=False)
    formula = Column(Text, nullable=False)
    calculation_date = Column(DateTime(timezone=True), nullable=False)
    id_business = Column(
        BigInteger,
        ForeignKey("booking.business.id_business"),
        nullable=False,
    )

    analytics_events = relationship(
        "AnalyticsEvent",
        back_populates="kpi",
        cascade="all, delete-orphan",
    )


__all__ = ["KpiLog"]
