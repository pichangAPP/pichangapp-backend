"""Business logic for analytics features."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repository import AnalyticsRepositoryError, fetch_revenue_summary
from app.schemas.analytics import DateRange, RevenueEntry, RevenueSummaryResponse

DEFAULT_DAY_WINDOW = 30


def _ensure_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _calculate_period_end(period_start: datetime, interval: str) -> datetime:
    period_start = _ensure_timezone(period_start)
    if interval == "day":
        return period_start + timedelta(days=1)
    if interval == "week":
        return period_start + timedelta(weeks=1)
    if interval == "month":
        year = period_start.year
        month = period_start.month
        if month == 12:
            return period_start.replace(year=year + 1, month=1, day=1)
        return period_start.replace(year=year, month=month + 1, day=1)
    raise ValueError(f"Unsupported interval '{interval}'")


class AnalyticsService:
    """Encapsulates analytics business logic."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_revenue_summary(
        self,
        *,
        start_date: Optional[date],
        end_date: Optional[date],
        currency: Optional[str],
        status: Optional[str],
    ) -> RevenueSummaryResponse:
        today = datetime.now(timezone.utc).date()
        if end_date is None:
            end_date = today
        if start_date is None:
            start_date = end_date - timedelta(days=DEFAULT_DAY_WINDOW - 1)
        if start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_date must be on or before end_date",
            )

        start_at = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        end_at = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)

        try:
            summary_data = fetch_revenue_summary(
                self._db,
                start_at=start_at,
                end_at=end_at,
                currency=currency,
                status=status,
            )
        except AnalyticsRepositoryError as exc:  # pragma: no cover - defensive programming
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to compute revenue summary",
            ) from exc

        return RevenueSummaryResponse(
            date_range=DateRange(start=start_at, end=end_at),
            daily=self._build_entries(summary_data["daily"], "day"),
            weekly=self._build_entries(summary_data["weekly"], "week"),
            monthly=self._build_entries(summary_data["monthly"], "month"),
        )

    def _build_entries(
        self,
        rows: List[dict],
        interval: str,
    ) -> List[RevenueEntry]:
        entries: List[RevenueEntry] = []
        for row in rows:
            period_start = _ensure_timezone(row["period_start"])
            entries.append(
                RevenueEntry(
                    period_start=period_start,
                    period_end=_calculate_period_end(period_start, interval),
                    total_amount=row["total_amount"],
                    currency=row["currency"],
                )
            )
        return entries


__all__ = ["AnalyticsService"]
