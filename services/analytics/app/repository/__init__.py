"""Repository helpers for the analytics service."""

from app.repository.analytics_repository import (
    AnalyticsRepositoryError,
    fetch_campus_daily_income,
    fetch_campus_daily_rent_traffic,
    fetch_campus_income_total,
    fetch_campus_overview,
    fetch_revenue_grouped_totals,
    fetch_revenue_summary,
)

__all__ = [
    "AnalyticsRepositoryError",
    "fetch_campus_daily_income",
    "fetch_campus_daily_rent_traffic",
    "fetch_campus_income_total",
    "fetch_campus_overview",
    "fetch_revenue_grouped_totals",
    "fetch_revenue_summary",
]
