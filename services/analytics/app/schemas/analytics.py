"""Analytics-related response models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List

from pydantic import BaseModel, Field


class DateRange(BaseModel):
    """Represents the date range used for a revenue aggregation request."""

    start: datetime = Field(..., description="Start datetime (inclusive) used for aggregation.")
    end: datetime = Field(..., description="End datetime (exclusive) used for aggregation.")


class RevenueEntry(BaseModel):
    """Revenue information for a specific period."""

    period_start: datetime = Field(..., description="Start of the aggregated period.")
    period_end: datetime = Field(..., description="End of the aggregated period.")
    total_amount: Decimal = Field(..., ge=Decimal("0"), description="Total revenue amount.")
    rent_count: int = Field(..., ge=0, description="Number of rents contributing to the total amount.")


class CampusRevenueSummary(BaseModel):
    """Aggregated revenue grouped by campus."""

    campus_id: int = Field(..., description="Identifier of the campus.")
    campus_name: str = Field(..., max_length=300, description="Display name of the campus.")
    daily: List[RevenueEntry]
    weekly: List[RevenueEntry]
    monthly: List[RevenueEntry]


class RevenueSummaryResponse(BaseModel):
    """Response model containing revenue grouped by campus and period."""

    date_range: DateRange
    campuses: List[CampusRevenueSummary]


__all__ = [
    "CampusRevenueSummary",
    "DateRange",
    "RevenueEntry",
    "RevenueSummaryResponse",
]
