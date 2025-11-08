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
    currency: str = Field(..., max_length=30, description="Currency code for the aggregated payments.")


class RevenueSummaryResponse(BaseModel):
    """Response model containing revenue grouped by different periods."""

    date_range: DateRange
    daily: List[RevenueEntry]
    weekly: List[RevenueEntry]
    monthly: List[RevenueEntry]


__all__ = ["DateRange", "RevenueEntry", "RevenueSummaryResponse"]
