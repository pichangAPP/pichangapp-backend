"""API routes for analytics operations."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.analytics import (
    OccupancyMetricsResponse,
    PeakHoursResponse,
    RentMetricsResponse,
    TopOccupancyResponse,
    CampusActiveReservationsResponse,
    CampusFieldUsageResponse,
    CampusFrequentClientsResponse,
    CampusRevenueMetricsResponse,
    RevenueSummaryResponse,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/revenue-summary", response_model=RevenueSummaryResponse)
def get_revenue_summary(
    start_date: Optional[date] = Query(
        None,
        description="Start date (inclusive) used to aggregate rents.",
    ),
    end_date: Optional[date] = Query(
        None,
        description="End date (inclusive) used to aggregate rents.",
    ),
    status: Optional[str] = Query(
        "paid",
        description=(
            "Restrict the aggregation to rents with the provided status. "
            "Defaults to 'paid'."
        ),
        min_length=1,
        max_length=30,
    ),
    db: Session = Depends(get_db),
) -> RevenueSummaryResponse:
    """Return revenue totals aggregated by day, week and month for each campus."""

    service = AnalyticsService(db)
    return service.get_revenue_summary(
        start_date=start_date,
        end_date=end_date,
        status=status,
)


@router.get(
    "/campuses/{campus_id}/revenue-metrics",
    response_model=CampusRevenueMetricsResponse,
)
def get_campus_revenue_metrics(
    campus_id: int,
    traffic_mode: Literal["monthly_weekday", "daily_last7"] = Query(
        "monthly_weekday",
        description=(
            "Traffic mode for last_seven_days_rent_traffic. "
            "'monthly_weekday' uses month-to-date totals by weekday; "
            "'daily_last7' uses real totals for each of the last seven dates."
        ),
    ),
    db: Session = Depends(get_db),
) -> CampusRevenueMetricsResponse:
    """Return detailed revenue metrics for the specified campus."""

    service = AnalyticsService(db)
    return service.get_campus_revenue_metrics(
        campus_id=campus_id,
        traffic_mode=traffic_mode,
    )


@router.get("/metrics/rents", response_model=RentMetricsResponse)
def get_rent_metrics(
    period: Literal["today", "week", "month", "date", "custom"] = Query(
        "month",
        description=(
            "Period mode: today, week, month, date (uses target_date), "
            "custom (uses start_date + end_date)."
        ),
    ),
    target_date: Optional[date] = Query(
        None,
        description="Specific date when period='date'.",
    ),
    start_date: Optional[date] = Query(
        None,
        description="Start date for custom range (inclusive).",
    ),
    end_date: Optional[date] = Query(
        None,
        description="End date for custom range (inclusive).",
    ),
    group_by: Literal["day", "week", "month", "status", "campus", "field", "sport"] = Query(
        "day",
        description="Grouping dimension for reservation/income metrics.",
    ),
    campus_id: Optional[int] = Query(None, description="Optional campus filter."),
    field_id: Optional[int] = Query(None, description="Optional field filter."),
    sport_id: Optional[int] = Query(None, description="Optional sport filter."),
    status: Optional[str] = Query(
        None,
        min_length=1,
        max_length=30,
        description="Optional rent status filter.",
    ),
    db: Session = Depends(get_db),
) -> RentMetricsResponse:
    """Reusable reservation count + income metrics with shared filters."""

    service = AnalyticsService(db)
    return service.get_rent_metrics(
        period=period,
        target_date=target_date,
        start_date=start_date,
        end_date=end_date,
        group_by=group_by,
        campus_id=campus_id,
        field_id=field_id,
        sport_id=sport_id,
        status=status,
    )


@router.get("/metrics/occupancy", response_model=OccupancyMetricsResponse)
def get_occupancy_metrics(
    period: Literal["today", "week", "month", "date", "custom"] = Query(
        "today",
        description=(
            "Period mode: today, week, month, date (uses target_date), "
            "custom (uses start_date + end_date)."
        ),
    ),
    target_date: Optional[date] = Query(
        None,
        description="Specific date when period='date'.",
    ),
    start_date: Optional[date] = Query(
        None,
        description="Start date for custom range (inclusive).",
    ),
    end_date: Optional[date] = Query(
        None,
        description="End date for custom range (inclusive).",
    ),
    campus_id: Optional[int] = Query(None, description="Optional campus filter."),
    field_id: Optional[int] = Query(None, description="Optional field filter."),
    sport_id: Optional[int] = Query(None, description="Optional sport filter."),
    status: Optional[str] = Query(
        None,
        min_length=1,
        max_length=30,
        description="Optional rent status filter.",
    ),
    db: Session = Depends(get_db),
) -> OccupancyMetricsResponse:
    """Reusable occupancy metrics for campus/field/sport scopes."""

    service = AnalyticsService(db)
    return service.get_occupancy_metrics(
        period=period,
        target_date=target_date,
        start_date=start_date,
        end_date=end_date,
        campus_id=campus_id,
        field_id=field_id,
        sport_id=sport_id,
        status=status,
    )


@router.get("/rankings/top-occupancy", response_model=TopOccupancyResponse)
def get_top_occupancy(
    scope: Literal["campus", "field", "sport"] = Query(
        "campus",
        description="Ranking scope.",
    ),
    period: Literal["today", "week", "month", "date", "custom"] = Query(
        "month",
        description=(
            "Period mode: today, week, month, date (uses target_date), "
            "custom (uses start_date + end_date)."
        ),
    ),
    target_date: Optional[date] = Query(
        None,
        description="Specific date when period='date'.",
    ),
    start_date: Optional[date] = Query(
        None,
        description="Start date for custom range (inclusive).",
    ),
    end_date: Optional[date] = Query(
        None,
        description="End date for custom range (inclusive).",
    ),
    campus_id: Optional[int] = Query(None, description="Optional campus filter."),
    field_id: Optional[int] = Query(None, description="Optional field filter."),
    sport_id: Optional[int] = Query(None, description="Optional sport filter."),
    status: Optional[str] = Query(
        None,
        min_length=1,
        max_length=30,
        description="Optional rent status filter.",
    ),
    limit: int = Query(10, ge=1, le=100, description="Maximum rows returned."),
    db: Session = Depends(get_db),
) -> TopOccupancyResponse:
    """Top occupancy ranking by campus, field or sport."""

    service = AnalyticsService(db)
    return service.get_top_occupancy(
        scope=scope,
        period=period,
        target_date=target_date,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        campus_id=campus_id,
        field_id=field_id,
        sport_id=sport_id,
        status=status,
    )


@router.get("/metrics/peak-hours", response_model=PeakHoursResponse)
def get_peak_hours(
    scope: Literal["all", "campus", "field", "sport"] = Query(
        "all",
        description="Peak-hour analysis scope.",
    ),
    period: Literal["today", "week", "month", "date", "custom"] = Query(
        "month",
        description=(
            "Period mode: today, week, month, date (uses target_date), "
            "custom (uses start_date + end_date)."
        ),
    ),
    target_date: Optional[date] = Query(
        None,
        description="Specific date when period='date'.",
    ),
    start_date: Optional[date] = Query(
        None,
        description="Start date for custom range (inclusive).",
    ),
    end_date: Optional[date] = Query(
        None,
        description="End date for custom range (inclusive).",
    ),
    campus_id: Optional[int] = Query(None, description="Campus filter."),
    field_id: Optional[int] = Query(None, description="Field filter."),
    sport_id: Optional[int] = Query(None, description="Sport filter."),
    status: Optional[str] = Query(
        None,
        min_length=1,
        max_length=30,
        description="Optional rent status filter.",
    ),
    limit: int = Query(10, ge=1, le=100, description="Top intersections to return."),
    db: Session = Depends(get_db),
) -> PeakHoursResponse:
    """Peak hours and weekday/hour intersections for reservations."""

    service = AnalyticsService(db)
    return service.get_peak_hours(
        scope=scope,
        period=period,
        target_date=target_date,
        start_date=start_date,
        end_date=end_date,
        campus_id=campus_id,
        field_id=field_id,
        sport_id=sport_id,
        status=status,
        limit=limit,
    )


@router.get(
    "/campuses/{campus_id}/top-clients",
    response_model=CampusFrequentClientsResponse,
)
def get_campus_frequent_clients(
    campus_id: int,
    limit: int = Query(
        10,
        ge=1,
        le=100,
        description="Maximum number of clients to return.",
    ),
    db: Session = Depends(get_db),
) -> CampusFrequentClientsResponse:
    """Return the most recurrent clients associated with the campus."""

    service = AnalyticsService(db)
    return service.get_campus_frequent_clients(campus_id=campus_id, limit=limit)


@router.get(
    "/campuses/{campus_id}/top-fields",
    response_model=CampusFieldUsageResponse,
)
def get_campus_top_fields(
    campus_id: int,
    limit: int = Query(
        5,
        ge=1,
        le=100,
        description="Maximum number of fields to return.",
    ),
    db: Session = Depends(get_db),
) -> CampusFieldUsageResponse:
    """Return the most frequently used fields for the campus this month."""

    service = AnalyticsService(db)
    return service.get_campus_top_fields(campus_id=campus_id, limit=limit)


@router.get(
    "/campuses/{campus_id}/active-reservations",
    response_model=CampusActiveReservationsResponse,
)
def get_campus_active_reservations(
    campus_id: int,
    target_date: Optional[date] = Query(
        None,
        description="Date to inspect (defaults to today in local timezone).",
    ),
    field_name: Optional[str] = Query(
        None,
        description="Optional field name filter (partial match).",
    ),
    limit: int = Query(
        100,
        ge=1,
        le=300,
        description="Maximum number of active reservations to return.",
    ),
    db: Session = Depends(get_db),
) -> CampusActiveReservationsResponse:
    """Return active reservations for the selected campus and date."""

    service = AnalyticsService(db)
    return service.get_campus_active_reservations(
        campus_id=campus_id,
        target_date=target_date or date.today(),
        field_name=field_name,
        limit=limit,
    )


__all__ = ["router"]
