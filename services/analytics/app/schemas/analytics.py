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
        ...,
        description=(
            "Seven consecutive dates ending today. By default each rent_count is "
            "the month-to-date total for that weekday; with traffic_mode="
            "'daily_last7', each rent_count is the real total for that date."
        ),
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


class FieldUsage(BaseModel):
    """Top usage info for a field."""

    field_id: int = Field(..., description="Identifier of the field.")
    field_name: str = Field(..., description="Name of the field.")
    usage_count: int = Field(..., ge=0, description="Number of rents for the field this month.")


class CampusFieldUsageResponse(BaseModel):
    """Most used fields for a campus during the current month."""

    campus_id: int = Field(..., description="Identifier of the campus.")
    campus_name: str = Field(..., description="Display name of the campus.")
    top_fields: List[FieldUsage] = Field(
        ..., description="Top used fields for the campus ordered by usage count."
    )


class ActiveReservation(BaseModel):
    """Active reservation detail for a campus/date window."""

    rent_id: int = Field(..., description="Identifier of the rent.")
    rent_status: str = Field(..., description="Status of the reservation.")
    field_id: int = Field(..., description="Identifier of the field.")
    field_name: str = Field(..., description="Name of the field.")
    start_time: datetime = Field(..., description="Reservation start datetime.")
    end_time: datetime = Field(..., description="Reservation end datetime.")
    user_id: Optional[int] = Field(None, description="Identifier of the renter user.")


class CampusActiveReservationsResponse(BaseModel):
    """Active reservations for a campus and target date."""

    campus_id: int = Field(..., description="Identifier of the campus.")
    campus_name: str = Field(..., description="Display name of the campus.")
    target_date: date = Field(..., description="Date used to filter reservations.")
    total_active_reservations: int = Field(
        ..., ge=0, description="Total active reservations in the selected date."
    )
    reservations: List[ActiveReservation] = Field(
        ..., description="Active reservations sorted by start time."
    )


class AnalyticsPeriodWindow(BaseModel):
    """Resolved datetime window used by metrics endpoints."""

    period: str = Field(..., description="Requested period mode.")
    start: datetime = Field(..., description="Start datetime (inclusive).")
    end: datetime = Field(..., description="End datetime (exclusive).")


class AnalyticsAppliedFilters(BaseModel):
    """Normalized filters applied to a metrics query."""

    campus_id: Optional[int] = Field(None, description="Campus filter.")
    field_id: Optional[int] = Field(None, description="Field filter.")
    sport_id: Optional[int] = Field(None, description="Sport filter.")
    status: Optional[str] = Field(None, description="Rent status filter.")


class AggregatedMetricRow(BaseModel):
    """Aggregated row for grouped reservation/income metrics."""

    group_key: str = Field(..., description="Stable grouping key.")
    group_label: str = Field(..., description="Human-friendly label.")
    reservation_count: int = Field(..., ge=0, description="Reservations in the group.")
    income_total: Decimal = Field(..., ge=Decimal("0"), description="Income for the group.")


class RentMetricsResponse(BaseModel):
    """Reusable grouped metrics for reservations and income."""

    period_window: AnalyticsPeriodWindow
    group_by: str = Field(..., description="Dimension used for grouping.")
    filters: AnalyticsAppliedFilters
    total_reservations: int = Field(..., ge=0)
    total_income: Decimal = Field(..., ge=Decimal("0"))
    rows: List[AggregatedMetricRow]


class OccupancyFieldPoint(BaseModel):
    """Per-field occupancy snapshot inside a period window."""

    campus_id: int
    campus_name: str
    field_id: int
    field_name: str
    sport_id: int
    sport_name: str
    field_status: str
    total_schedules: int = Field(..., ge=0)
    reservation_count: int = Field(..., ge=0)
    active_reservation_count: int = Field(..., ge=0)
    income_total: Decimal = Field(..., ge=Decimal("0"))
    is_occupied: bool


class OccupancySummary(BaseModel):
    """Global occupancy values for the selected filters/window."""

    total_fields: int = Field(..., ge=0)
    occupied_fields: int = Field(..., ge=0)
    occupancy_rate: Decimal = Field(..., ge=Decimal("0"))
    total_schedules: int = Field(..., ge=0)
    total_reservations: int = Field(..., ge=0)
    total_income: Decimal = Field(..., ge=Decimal("0"))


class OccupancyMetricsResponse(BaseModel):
    """Occupancy metrics by field with global summary."""

    period_window: AnalyticsPeriodWindow
    filters: AnalyticsAppliedFilters
    summary: OccupancySummary
    fields: List[OccupancyFieldPoint]


class TopOccupancyEntity(BaseModel):
    """Top entity row for occupancy rankings."""

    scope: str = Field(..., description="Ranking scope: campus/field/sport.")
    entity_id: int = Field(..., ge=1)
    entity_name: str
    campus_id: Optional[int] = None
    campus_name: Optional[str] = None
    reservation_count: int = Field(..., ge=0)
    income_total: Decimal = Field(..., ge=Decimal("0"))


class TopOccupancyResponse(BaseModel):
    """Top occupancy ranking response."""

    period_window: AnalyticsPeriodWindow
    scope: str
    limit: int = Field(..., ge=1)
    filters: AnalyticsAppliedFilters
    rows: List[TopOccupancyEntity]


class PeakHourPoint(BaseModel):
    """Reservations grouped by hour."""

    hour: int = Field(..., ge=0, le=23)
    reservation_count: int = Field(..., ge=0)


class PeakIntersectionPoint(BaseModel):
    """Top weekday + hour intersection row."""

    weekday: str
    hour: int = Field(..., ge=0, le=23)
    reservation_count: int = Field(..., ge=0)


class PeakHoursResponse(BaseModel):
    """Peak-hours analytics with hourly distribution and intersections."""

    period_window: AnalyticsPeriodWindow
    scope: str
    filters: AnalyticsAppliedFilters
    top_intersections: List[PeakIntersectionPoint]
    hourly_distribution: List[PeakHourPoint]


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
    "FieldUsage",
    "CampusFieldUsageResponse",
    "ActiveReservation",
    "CampusActiveReservationsResponse",
    "AnalyticsPeriodWindow",
    "AnalyticsAppliedFilters",
    "AggregatedMetricRow",
    "RentMetricsResponse",
    "OccupancyFieldPoint",
    "OccupancySummary",
    "OccupancyMetricsResponse",
    "TopOccupancyEntity",
    "TopOccupancyResponse",
    "PeakHourPoint",
    "PeakIntersectionPoint",
    "PeakHoursResponse",
]
