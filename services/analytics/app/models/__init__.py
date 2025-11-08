"""Database models for the analytics service."""

from app.models.analytics_event import AnalyticsEvent
from app.models.kpi_log import KpiLog

__all__ = ["AnalyticsEvent", "KpiLog"]
