"""Repository helpers for the analytics service."""

from app.repository.analytics_repository import (
    AnalyticsRepositoryError,
    fetch_campus_daily_income,
    fetch_campus_daily_rent_traffic,
    fetch_campus_income_total,
    fetch_campus_overview,
    fetch_campus_top_clients,
    fetch_revenue_grouped_totals,
    fetch_revenue_summary,
)

from app.repository.feedback_repository import (
    FeedbackRepositoryError,
    RentFeedbackContext,
    create_feedback,
    delete_feedback,
    fetch_rent_context,
    get_feedback,
    get_feedback_by_rent_and_user,
    list_feedback_by_field,
    recalculate_campus_rating,
)

__all__ = [
    "FeedbackRepositoryError",
    "RentFeedbackContext",
    "create_feedback",
    "delete_feedback",
    "fetch_rent_context",
    "get_feedback",
    "get_feedback_by_rent_and_user",
    "list_feedback_by_field",
    "recalculate_campus_rating",
    "AnalyticsRepositoryError",
    "fetch_campus_daily_income",
    "fetch_campus_daily_rent_traffic",
    "fetch_campus_income_total",
    "fetch_campus_overview",
    "fetch_campus_top_clients",
    "fetch_revenue_grouped_totals",
    "fetch_revenue_summary",
]
