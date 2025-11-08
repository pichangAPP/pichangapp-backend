"""API routes for analytics operations."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.analytics import RevenueSummaryResponse
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


__all__ = ["router"]
