"""Pydantic schemas for the analytics service."""

from app.schemas.feedback import FeedbackBase, FeedbackCreate, FeedbackResponse

from app.schemas.analytics import (
    CampusRevenueSummary,
    DateRange,
    RevenueEntry,
    RevenueSummaryResponse,
)

__all__ = [
    "FeedbackBase",
    "FeedbackCreate",
    "FeedbackResponse",
    "CampusRevenueSummary",
    "DateRange",
    "RevenueEntry",
    "RevenueSummaryResponse",
]
