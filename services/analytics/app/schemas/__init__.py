"""Pydantic schemas for the analytics service."""

from app.schemas.analytics import (
    CampusRevenueSummary,
    DateRange,
    RevenueEntry,
    RevenueSummaryResponse,
)

__all__ = [
    "CampusRevenueSummary",
    "DateRange",
    "RevenueEntry",
    "RevenueSummaryResponse",
]
