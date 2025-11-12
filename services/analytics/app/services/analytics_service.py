"""Business logic for analytics features."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repository import (
    AnalyticsRepositoryError,
    fetch_campus_daily_income,
    fetch_campus_daily_rent_traffic,
    fetch_campus_income_total,
    fetch_campus_overview,
    fetch_revenue_summary,
)
from app.schemas.analytics import (
    CampusRevenueSummary,
    CampusRevenueMetricsResponse,
    DateRange,
    FieldAvailability,
    IncomePoint,
    RevenueEntry,
    RentTrafficPoint,
    RevenueSummaryResponse,
)

DEFAULT_DAY_WINDOW = 30
LOCAL_TIMEZONE = timezone(timedelta(hours=-5))


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
        status: Optional[str],
    ) -> RevenueSummaryResponse:
        today = datetime.now(LOCAL_TIMEZONE).date()
        if end_date is None:
            end_date = today
        if start_date is None:
            start_date = end_date - timedelta(days=DEFAULT_DAY_WINDOW - 1)
        if start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_date must be on or before end_date",
            )

        start_at = datetime.combine(start_date, time.min, tzinfo=LOCAL_TIMEZONE)
        end_at = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=LOCAL_TIMEZONE)

        try:
            summary_data = fetch_revenue_summary(
                self._db,
                start_at=start_at,
                end_at=end_at,
                status=status,
            )
        except AnalyticsRepositoryError as exc:  # pragma: no cover - defensive programming
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to compute revenue summary",
            ) from exc

        campuses = self._build_campus_summaries(summary_data)

        return RevenueSummaryResponse(
            date_range=DateRange(start=start_at, end=end_at),
            campuses=campuses,
        )

    def get_campus_revenue_metrics(self, campus_id: int) -> CampusRevenueMetricsResponse:
        """Return detailed revenue metrics for the specified campus."""

        now = datetime.now(LOCAL_TIMEZONE)
        today = now.date()
        start_of_today = datetime.combine(today, time.min, tzinfo=LOCAL_TIMEZONE)
        start_of_tomorrow = start_of_today + timedelta(days=1)

        week_start_date = today - timedelta(days=today.weekday())
        week_start = datetime.combine(week_start_date, time.min, tzinfo=LOCAL_TIMEZONE)
        week_end = week_start + timedelta(days=7)

        month_start = datetime(2025, 11, 1, 0, 0, tzinfo=LOCAL_TIMEZONE)
        month_start_date = month_start.date()
        month_end = _calculate_period_end(month_start, "month")

        seven_day_start = start_of_today - timedelta(days=6)
        seven_day_end = start_of_tomorrow

        week_range_end = min(week_end, start_of_tomorrow)
        month_range_end = min(month_end, start_of_tomorrow)

        try:
            campus_overview = fetch_campus_overview(self._db, campus_id=campus_id)
        except AnalyticsRepositoryError as exc:  # pragma: no cover - defensive programming
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to obtain campus information",
            ) from exc

        if campus_overview is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campus not found",
            )

        try:
            today_total = fetch_campus_income_total(
                self._db,
                campus_id=campus_id,
                start_at=start_of_today,
                end_at=start_of_tomorrow,
            )
            week_total = fetch_campus_income_total(
                self._db,
                campus_id=campus_id,
                start_at=week_start,
                end_at=week_range_end,
            )
            month_total = fetch_campus_income_total(
                self._db,
                campus_id=campus_id,
                start_at=month_start,
                end_at=month_range_end,
            )

            weekly_daily_income_rows = fetch_campus_daily_income(
                self._db,
                campus_id=campus_id,
                start_at=week_start,
                end_at=week_range_end,
            )
            monthly_daily_income_rows = fetch_campus_daily_income(
                self._db,
                campus_id=campus_id,
                start_at=month_start,
                end_at=month_range_end,
            )

            seven_day_traffic_rows = fetch_campus_daily_rent_traffic(
                self._db,
                campus_id=campus_id,
                start_at=seven_day_start,
                end_at=seven_day_end,
            )
        except AnalyticsRepositoryError as exc:  # pragma: no cover - defensive programming
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to compute campus revenue metrics",
            ) from exc

        week_end_inclusive = (week_range_end - timedelta(days=1)).date()
        month_end_inclusive = (month_range_end - timedelta(days=1)).date()

        weekly_daily_income = self._build_daily_income_series(
            start_date=week_start_date,
            end_date=week_end_inclusive,
            rows=weekly_daily_income_rows,
        )
        monthly_daily_income = self._build_daily_income_series(
            start_date=month_start_date,
            end_date=month_end_inclusive,
            rows=monthly_daily_income_rows,
        )
        seven_day_traffic = self._build_daily_traffic_series(
            start_date=seven_day_start.date(),
            days=7,
            rows=seven_day_traffic_rows,
        )

        fields = FieldAvailability(
            available=int(campus_overview["available_fields"]),
            total=int(campus_overview["total_fields"]),
        )

        return CampusRevenueMetricsResponse(
            campus_id=campus_overview["campus_id"],
            campus_name=campus_overview["campus_name"],
            today_income_total=self._normalize_decimal(today_total),
            weekly_income_total=self._normalize_decimal(week_total),
            monthly_income_total=self._normalize_decimal(month_total),
            weekly_daily_income=weekly_daily_income,
            monthly_daily_income=monthly_daily_income,
            last_seven_days_rent_traffic=seven_day_traffic,
            fields=fields,
        )

    def _build_campus_summaries(
        self,
        summary_data: Dict[str, List[dict]],
    ) -> List[CampusRevenueSummary]:
        campuses: Dict[int, CampusRevenueSummary] = {}
        for interval_name, rows in summary_data.items():
            for row in rows:
                campus_id = int(row["campus_id"])
                campus = campuses.get(campus_id)
                if campus is None:
                    campus = CampusRevenueSummary(
                        campus_id=campus_id,
                        campus_name=row["campus_name"],
                        daily=[],
                        weekly=[],
                        monthly=[],
                    )
                    campuses[campus_id] = campus

                entry = self._build_entry(row, interval_name)
                getattr(campus, interval_name).append(entry)

        return sorted(
            campuses.values(),
            key=lambda campus: campus.campus_name.lower(),
        )

    def _build_entry(self, row: dict, interval: str) -> RevenueEntry:
        period_start = _ensure_timezone(row["period_start"])
        return RevenueEntry(
            period_start=period_start,
            period_end=_calculate_period_end(period_start, interval),
            total_amount=row["total_amount"],
            rent_count=int(row["rent_count"]),
        )

    def _build_daily_income_series(
        self,
        *,
        start_date: date,
        end_date: date,
        rows: List[Dict[str, object]],
    ) -> List[IncomePoint]:
        lookup: Dict[date, Decimal] = {}
        for row in rows:
            period_start = _ensure_timezone(row["period_start"])
            lookup[period_start.date()] = self._normalize_decimal(row["total_amount"])

        series: List[IncomePoint] = []
        current_day = start_date
        while current_day <= end_date:
            amount = lookup.get(current_day, Decimal("0"))
            series.append(IncomePoint(record_date=current_day, total_amount=amount))
            current_day += timedelta(days=1)
        return series

    def _build_daily_traffic_series(
        self,
        *,
        start_date: date,
        days: int,
        rows: List[Dict[str, object]],
    ) -> List[RentTrafficPoint]:
        lookup: Dict[date, int] = {}
        for row in rows:
            period_start = _ensure_timezone(row["period_start"])
            lookup[period_start.date()] = int(row["rent_count"])

        weekday_names = [
            "lunes",
            "martes",
            "miercoles",
            "jueves",
            "viernes",
            "sabado",
            "domingo",
        ]

        series: List[RentTrafficPoint] = []
        for offset in range(days):
            day = start_date + timedelta(days=offset)
            rent_count = lookup.get(day, 0)
            weekday = weekday_names[day.weekday() % len(weekday_names)]
            series.append(
                RentTrafficPoint(record_date=day, weekday=weekday, rent_count=rent_count)
            )
        return series

    @staticmethod
    def _normalize_decimal(value: Decimal) -> Decimal:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value)) if value is not None else Decimal("0")


__all__ = ["AnalyticsService"]
