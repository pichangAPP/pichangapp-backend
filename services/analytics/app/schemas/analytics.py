"""Analytics-related response models."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

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


class IncomePoint(BaseModel):
    """Represents an income value for a specific day."""

    record_date: date = Field(..., description="Date of the aggregated income.")
    total_amount: Decimal = Field(
        ..., ge=Decimal("0"), description="Total income generated on the given day."
    )


class RentTrafficPoint(BaseModel):
    """Represents the number of rents registered for a specific day."""

    record_date: date = Field(..., description="Date corresponding to the rent activity.")
    weekday: str = Field(..., description="Weekday name for the date.")
    rent_count: int = Field(..., ge=0, description="Total number of rents recorded on the date.")


class FieldAvailability(BaseModel):
    """Availability information for campus fields."""

    available: int = Field(..., ge=0, description="Number of available fields.")
    total: int = Field(..., ge=0, description="Total number of fields in the campus.")


class CampusRevenueMetricsResponse(BaseModel):
    """Detailed revenue metrics for a specific campus."""

    campus_id: int = Field(..., description="Identifier of the campus.")
    campus_name: str = Field(..., max_length=300, description="Display name of the campus.")
    today_income_total: Decimal = Field(
        ..., ge=Decimal("0"), description="Total income generated during the current day."
    )
    weekly_income_total: Decimal = Field(
        ..., ge=Decimal("0"), description="Total income generated during the current week."
    )
    monthly_income_total: Decimal = Field(
        ..., ge=Decimal("0"), description="Total income generated during the current month."
    )
    weekly_daily_income: List[IncomePoint] = Field(
        ..., description="Daily income entries for the current week."
    )
    monthly_daily_income: List[IncomePoint] = Field(
        ..., description="Daily income entries for the current month."
    )
    last_seven_days_rent_traffic: List[RentTrafficPoint] = Field(
        ..., description="Daily rent traffic for the last seven days."
    )
    fields: FieldAvailability = Field(..., description="Field availability summary for the campus.")


class FrequentClient(BaseModel):
    """Profile of a client ordered by rent frequency."""

    name: str = Field(..., description="Full name of the client.")
    email: str = Field(..., description="Email address associated with the client.")
    phone: str = Field(..., description="Phone number associated with the client.")
    image_url: Optional[str] = Field(
        None, description="Optional avatar or profile image URL for the client."
    )
    city: Optional[str] = Field(None, description="City associated with the client.")
    district: Optional[str] = Field(None, description="District associated with the client.")
    rent_count: int = Field(..., ge=0, description="Number of rents associated with the client.")


class CampusFrequentClientsResponse(BaseModel):
    """Frequent clients for a given campus."""

    campus_id: int = Field(..., description="Identifier of the campus.")
    campus_name: str = Field(..., max_length=300, description="Display name of the campus.")
    frequent_clients: List[FrequentClient] = Field(
        ..., description="List of frequent clients ordered by rent count."
    )


__all__ = [
    "CampusRevenueSummary",
    "CampusRevenueMetricsResponse",
    "DateRange",
    "FieldAvailability",
    "IncomePoint",
    "RevenueEntry",
    "RentTrafficPoint",
    "RevenueSummaryResponse",
    "FrequentClient",
    "CampusFrequentClientsResponse",
]
