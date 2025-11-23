"""API routes for analytics operations."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.analytics import (
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
    db: Session = Depends(get_db),
) -> CampusRevenueMetricsResponse:
    """Return detailed revenue metrics for the specified campus."""

    service = AnalyticsService(db)
    return service.get_campus_revenue_metrics(campus_id=campus_id)


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


__all__ = ["router"]
