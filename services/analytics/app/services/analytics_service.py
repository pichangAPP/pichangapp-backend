"""Business logic for analytics features."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.error_codes import (
    ANALYTICS_INVALID_DATE_RANGE,
    ANALYTICS_INVALID_LIMIT,
    ANALYTICS_INVALID_TRAFFIC_MODE,
    ANALYTICS_REPOSITORY_ERROR,
    CAMPUS_NOT_FOUND,
    http_error,
)
from app.repository import (
    AnalyticsRepositoryError,
    fetch_campus_active_reservations,
    fetch_campus_daily_income,
    fetch_campus_daily_rent_traffic,
    fetch_campus_income_total,
    fetch_campus_overview,
    fetch_campus_top_clients,
    fetch_campus_top_fields,
    fetch_field_occupancy_snapshot,
    fetch_grouped_rent_metrics,
    fetch_peak_hour_intersections,
    fetch_top_occupancy_entities,
    fetch_revenue_summary,
)
from app.schemas.analytics import (
    ActiveReservation,
    AggregatedMetricRow,
    AnalyticsAppliedFilters,
    AnalyticsPeriodWindow,
    CampusActiveReservationsResponse,
    CampusRevenueSummary,
    CampusRevenueMetricsResponse,
    DateRange,
    FieldAvailability,
    IncomePoint,
    OccupancyFieldPoint,
    OccupancyMetricsResponse,
    OccupancySummary,
    PeakHourPoint,
    PeakHoursResponse,
    PeakIntersectionPoint,
    RevenueEntry,
    RentTrafficPoint,
    RevenueSummaryResponse,
    CampusFrequentClientsResponse,
    FrequentClient,
    FieldUsage,
    CampusFieldUsageResponse,
    RentMetricsResponse,
    TopOccupancyEntity,
    TopOccupancyResponse,
)

DEFAULT_DAY_WINDOW = 30
LOCAL_TIMEZONE = timezone(timedelta(hours=-5))
TRAFFIC_MODE_MONTHLY_WEEKDAY = "monthly_weekday"
TRAFFIC_MODE_DAILY_LAST7 = "daily_last7"
PERIOD_TODAY = "today"
PERIOD_WEEK = "week"
PERIOD_MONTH = "month"
PERIOD_DATE = "date"
PERIOD_CUSTOM = "custom"


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

    def _apply_read_only_tx_guards(self) -> None:
        """Configure transaction guards to reduce lock waits in analytics reads."""
        self._db.execute(text("SET LOCAL TRANSACTION READ ONLY"))

    def _resolve_period_window(
        self,
        *,
        period: str,
        target_date: Optional[date],
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> tuple[datetime, datetime]:
        now = datetime.now(LOCAL_TIMEZONE)
        today = now.date()

        if period == PERIOD_TODAY:
            start = datetime.combine(today, time.min, tzinfo=LOCAL_TIMEZONE)
            end = start + timedelta(days=1)
            return start, end

        if period == PERIOD_WEEK:
            week_start = today - timedelta(days=today.weekday())
            start = datetime.combine(week_start, time.min, tzinfo=LOCAL_TIMEZONE)
            end = datetime.combine(today + timedelta(days=1), time.min, tzinfo=LOCAL_TIMEZONE)
            return start, end

        if period == PERIOD_MONTH:
            start = datetime(now.year, now.month, 1, 0, 0, tzinfo=LOCAL_TIMEZONE)
            end = datetime.combine(today + timedelta(days=1), time.min, tzinfo=LOCAL_TIMEZONE)
            return start, end

        if period == PERIOD_DATE:
            if target_date is None:
                raise http_error(
                    ANALYTICS_INVALID_DATE_RANGE,
                    detail="target_date is required when period='date'",
                )
            start = datetime.combine(target_date, time.min, tzinfo=LOCAL_TIMEZONE)
            end = start + timedelta(days=1)
            return start, end

        if period == PERIOD_CUSTOM:
            if start_date is None or end_date is None:
                raise http_error(
                    ANALYTICS_INVALID_DATE_RANGE,
                    detail="start_date and end_date are required when period='custom'",
                )
            if start_date > end_date:
                raise http_error(
                    ANALYTICS_INVALID_DATE_RANGE,
                    detail="start_date must be on or before end_date",
                )
            start = datetime.combine(start_date, time.min, tzinfo=LOCAL_TIMEZONE)
            end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=LOCAL_TIMEZONE)
            return start, end

        raise http_error(
            ANALYTICS_INVALID_DATE_RANGE,
            detail="period must be one of: today, week, month, date, custom",
        )

    @staticmethod
    def _build_filters(
        *,
        campus_id: Optional[int],
        field_id: Optional[int],
        sport_id: Optional[int],
        status: Optional[str],
    ) -> AnalyticsAppliedFilters:
        return AnalyticsAppliedFilters(
            campus_id=campus_id,
            field_id=field_id,
            sport_id=sport_id,
            status=status,
        )

    def get_revenue_summary(
        self,
        *,
        start_date: Optional[date],
        end_date: Optional[date],
        status: Optional[str],
    ) -> RevenueSummaryResponse:
        self._apply_read_only_tx_guards()
        today = datetime.now(LOCAL_TIMEZONE).date()
        if end_date is None:
            end_date = today
        if start_date is None:
            start_date = end_date - timedelta(days=DEFAULT_DAY_WINDOW - 1)
        if start_date > end_date:
            raise http_error(
                ANALYTICS_INVALID_DATE_RANGE,
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
            raise http_error(
                ANALYTICS_REPOSITORY_ERROR,
                detail="Unable to compute revenue summary",
            ) from exc

        campuses = self._build_campus_summaries(summary_data)

        return RevenueSummaryResponse(
            date_range=DateRange(start=start_at, end=end_at),
            campuses=campuses,
        )

    def get_campus_revenue_metrics(
        self,
        campus_id: int,
        *,
        traffic_mode: str = TRAFFIC_MODE_MONTHLY_WEEKDAY,
        status: Optional[str] = None,
        statuses: Optional[Sequence[str]] = None,
    ) -> CampusRevenueMetricsResponse:
        """Return detailed revenue metrics for the specified campus."""
        self._apply_read_only_tx_guards()

        now = datetime.now(LOCAL_TIMEZONE)
        today = now.date()
        start_of_today = datetime.combine(today, time.min, tzinfo=LOCAL_TIMEZONE)
        start_of_tomorrow = start_of_today + timedelta(days=1)

        # Build comparable windows so income/traffic charts always align to current day:
        # - week starts on Monday and is capped to today to avoid future gaps
        # - month starts on the first day and is capped the same way
        # - seven_day_* always spans the last 7 calendar days
        week_start_date = today - timedelta(days=today.weekday())
        week_start = datetime.combine(week_start_date, time.min, tzinfo=LOCAL_TIMEZONE)
        week_end = week_start + timedelta(days=7)

        month_start = datetime(now.year, now.month, 1, 0, 0, tzinfo=LOCAL_TIMEZONE)
        month_start_date = month_start.date()
        month_end = _calculate_period_end(month_start, "month")

        seven_day_start = start_of_today - timedelta(days=6)
        seven_day_end = start_of_tomorrow
        week_range_end = min(week_end, start_of_tomorrow)
        month_range_end = min(month_end, start_of_tomorrow)

        try:
            campus_overview = fetch_campus_overview(self._db, campus_id=campus_id)
        except AnalyticsRepositoryError as exc:  #defensive programming
            raise http_error(
                ANALYTICS_REPOSITORY_ERROR,
                detail="Unable to obtain campus information",
            ) from exc

        if campus_overview is None:
            raise http_error(CAMPUS_NOT_FOUND, detail="Campus not found")

        try:
            today_total = fetch_campus_income_total(
                self._db,
                campus_id=campus_id,
                start_at=start_of_today,
                end_at=start_of_tomorrow,
                status=status,
                statuses=statuses,
            )
            week_total = fetch_campus_income_total(
                self._db,
                campus_id=campus_id,
                start_at=week_start,
                end_at=week_range_end,
                status=status,
                statuses=statuses,
            )
            month_total = fetch_campus_income_total(
                self._db,
                campus_id=campus_id,
                start_at=month_start,
                end_at=month_range_end,
                status=status,
                statuses=statuses,
            )

            weekly_daily_income_rows = fetch_campus_daily_income(
                self._db,
                campus_id=campus_id,
                start_at=week_start,
                end_at=week_range_end,
                status=status,
                statuses=statuses,
            )
            monthly_daily_income_rows = fetch_campus_daily_income(
                self._db,
                campus_id=campus_id,
                start_at=month_start,
                end_at=month_range_end,
                status=status,
                statuses=statuses,
            )

            if traffic_mode == TRAFFIC_MODE_DAILY_LAST7:
                traffic_rows = fetch_campus_daily_rent_traffic(
                    self._db,
                    campus_id=campus_id,
                    start_at=seven_day_start,
                    end_at=seven_day_end,
                )
            elif traffic_mode == TRAFFIC_MODE_MONTHLY_WEEKDAY:
                traffic_rows = fetch_campus_daily_rent_traffic(
                    self._db,
                    campus_id=campus_id,
                    start_at=month_start,
                    end_at=month_range_end,
                )
            else:
                raise http_error(
                    ANALYTICS_INVALID_TRAFFIC_MODE,
                    detail=(
                        "traffic_mode must be one of: "
                        f"'{TRAFFIC_MODE_MONTHLY_WEEKDAY}', '{TRAFFIC_MODE_DAILY_LAST7}'"
                    ),
                )
        except AnalyticsRepositoryError as exc:  #defensive programming
            raise http_error(
                ANALYTICS_REPOSITORY_ERROR,
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
        if traffic_mode == TRAFFIC_MODE_DAILY_LAST7:
            seven_day_traffic = self._build_last_seven_days_daily_traffic_series(
                start_date=seven_day_start.date(),
                days=7,
                rows=traffic_rows,
            )
        else:
            seven_day_traffic = self._build_last_seven_days_month_traffic_series(
                start_date=seven_day_start.date(),
                days=7,
                rows=traffic_rows,
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

    def get_campus_top_fields(
        self,
        *,
        campus_id: int,
        limit: int,
    ) -> CampusFieldUsageResponse:
        """Return the most-used fields for the current month."""
        self._apply_read_only_tx_guards()

        now = datetime.now(LOCAL_TIMEZONE)
        month_start = datetime(now.year, now.month, 1, tzinfo=LOCAL_TIMEZONE)
        month_end = _calculate_period_end(month_start, "month")

        try:
            field_rows = fetch_campus_top_fields(
                self._db,
                campus_id=campus_id,
                start_at=month_start,
                end_at=month_end,
                limit=limit,
            )
        except AnalyticsRepositoryError as exc:
            raise http_error(
                ANALYTICS_REPOSITORY_ERROR,
                detail="Unable to fetch field usage",
            ) from exc

        try:
            campus_overview = fetch_campus_overview(self._db, campus_id=campus_id)
        except AnalyticsRepositoryError as exc:
            raise http_error(
                ANALYTICS_REPOSITORY_ERROR,
                detail="Unable to retrieve campus info",
            ) from exc

        if campus_overview is None:
            raise http_error(CAMPUS_NOT_FOUND, detail="Campus not found")

        top_fields = [
            FieldUsage(
                field_id=row["field_id"],
                field_name=row["field_name"],
                usage_count=row["usage_count"],
            )
            for row in field_rows
        ]

        return CampusFieldUsageResponse(
            campus_id=campus_overview["campus_id"],
            campus_name=campus_overview["campus_name"],
            top_fields=top_fields,
        )

    def get_campus_frequent_clients(
        self,
        campus_id: int,
        limit: int,
    ) -> CampusFrequentClientsResponse:
        """Return the most frequent clients for the specified campus."""
        self._apply_read_only_tx_guards()

        if limit < 1 or limit > 100:
            raise http_error(
                ANALYTICS_INVALID_LIMIT,
                detail="limit must be between 1 and 100",
            )

        try:
            campus_overview = fetch_campus_overview(self._db, campus_id=campus_id)
        except AnalyticsRepositoryError as exc:
            raise http_error(
                ANALYTICS_REPOSITORY_ERROR,
                detail="Unable to obtain campus information",
            ) from exc

        if campus_overview is None:
            raise http_error(CAMPUS_NOT_FOUND, detail="Campus not found")

        try:
            client_rows = fetch_campus_top_clients(
                self._db,
                campus_id=campus_id,
                limit=limit,
            )
        except AnalyticsRepositoryError as exc:
            raise http_error(
                ANALYTICS_REPOSITORY_ERROR,
                detail="Unable to compute frequent clients",
            ) from exc

        frequent_clients = self._build_frequent_clients(client_rows)

        return CampusFrequentClientsResponse(
            campus_id=campus_overview["campus_id"],
            campus_name=campus_overview["campus_name"],
            frequent_clients=frequent_clients,
        )

    def get_campus_active_reservations(
        self,
        *,
        campus_id: int,
        target_date: date,
        field_name: Optional[str] = None,
        limit: int = 100,
    ) -> CampusActiveReservationsResponse:
        """Return active reservations for a campus on a target date."""
        self._apply_read_only_tx_guards()

        day_start = datetime.combine(target_date, time.min, tzinfo=LOCAL_TIMEZONE)
        day_end = day_start + timedelta(days=1)

        try:
            campus_overview = fetch_campus_overview(self._db, campus_id=campus_id)
        except AnalyticsRepositoryError as exc:
            raise http_error(
                ANALYTICS_REPOSITORY_ERROR,
                detail="Unable to obtain campus information",
            ) from exc

        if campus_overview is None:
            raise http_error(CAMPUS_NOT_FOUND, detail="Campus not found")

        try:
            rows = fetch_campus_active_reservations(
                self._db,
                campus_id=campus_id,
                start_at=day_start,
                end_at=day_end,
                field_name=field_name,
                limit=limit,
            )
        except AnalyticsRepositoryError as exc:
            raise http_error(
                ANALYTICS_REPOSITORY_ERROR,
                detail="Unable to fetch active reservations",
            ) from exc

        reservations = [
            ActiveReservation(
                rent_id=int(row["rent_id"]),
                rent_status=str(row["rent_status"]),
                field_id=int(row["field_id"]),
                field_name=str(row["field_name"] or "Cancha"),
                start_time=_ensure_timezone(row["start_time"]),
                end_time=_ensure_timezone(row["end_time"]),
                user_id=int(row["user_id"]) if row.get("user_id") is not None else None,
            )
            for row in rows
        ]

        return CampusActiveReservationsResponse(
            campus_id=campus_overview["campus_id"],
            campus_name=campus_overview["campus_name"],
            target_date=target_date,
            total_active_reservations=len(reservations),
            reservations=reservations,
        )

    def get_rent_metrics(
        self,
        *,
        period: str,
        target_date: Optional[date],
        start_date: Optional[date],
        end_date: Optional[date],
        group_by: str,
        campus_id: Optional[int],
        field_id: Optional[int],
        sport_id: Optional[int],
        status: Optional[str],
    ) -> RentMetricsResponse:
        self._apply_read_only_tx_guards()
        start_at, end_at = self._resolve_period_window(
            period=period,
            target_date=target_date,
            start_date=start_date,
            end_date=end_date,
        )
        try:
            grouped_rows = fetch_grouped_rent_metrics(
                self._db,
                start_at=start_at,
                end_at=end_at,
                group_by=group_by,
                campus_id=campus_id,
                field_id=field_id,
                sport_id=sport_id,
                status=status,
            )
        except (AnalyticsRepositoryError, ValueError) as exc:
            raise http_error(
                ANALYTICS_REPOSITORY_ERROR,
                detail="Unable to compute grouped rent metrics",
            ) from exc

        rows = [
            AggregatedMetricRow(
                group_key=str(row["group_key"]),
                group_label=str(row["group_label"]),
                reservation_count=int(row["reservation_count"]),
                income_total=self._normalize_decimal(row["income_total"]),
            )
            for row in grouped_rows
        ]

        total_reservations = sum(row.reservation_count for row in rows)
        total_income = sum((row.income_total for row in rows), Decimal("0"))
        return RentMetricsResponse(
            period_window=AnalyticsPeriodWindow(period=period, start=start_at, end=end_at),
            group_by=group_by,
            filters=self._build_filters(
                campus_id=campus_id,
                field_id=field_id,
                sport_id=sport_id,
                status=status,
            ),
            total_reservations=total_reservations,
            total_income=total_income,
            rows=rows,
        )

    def get_occupancy_metrics(
        self,
        *,
        period: str,
        target_date: Optional[date],
        start_date: Optional[date],
        end_date: Optional[date],
        campus_id: Optional[int],
        field_id: Optional[int],
        sport_id: Optional[int],
        status: Optional[str],
    ) -> OccupancyMetricsResponse:
        self._apply_read_only_tx_guards()
        start_at, end_at = self._resolve_period_window(
            period=period,
            target_date=target_date,
            start_date=start_date,
            end_date=end_date,
        )
        try:
            rows = fetch_field_occupancy_snapshot(
                self._db,
                start_at=start_at,
                end_at=end_at,
                campus_id=campus_id,
                field_id=field_id,
                sport_id=sport_id,
                status=status,
            )
        except AnalyticsRepositoryError as exc:
            raise http_error(
                ANALYTICS_REPOSITORY_ERROR,
                detail="Unable to compute occupancy metrics",
            ) from exc

        field_points = [
            OccupancyFieldPoint(
                campus_id=int(row["campus_id"]),
                campus_name=str(row["campus_name"]),
                field_id=int(row["field_id"]),
                field_name=str(row["field_name"]),
                sport_id=int(row["sport_id"]),
                sport_name=str(row["sport_name"]),
                field_status=str(row["field_status"]),
                total_schedules=int(row["total_schedules"]),
                reservation_count=int(row["reservation_count"]),
                active_reservation_count=int(row["active_reservation_count"]),
                income_total=self._normalize_decimal(row["income_total"]),
                is_occupied=(
                    int(row["active_reservation_count"]) > 0
                    or str(row["field_status"]).strip().lower() == "occupied"
                ),
            )
            for row in rows
        ]

        total_fields = len(field_points)
        occupied_fields = sum(1 for row in field_points if row.is_occupied)
        total_schedules = sum(row.total_schedules for row in field_points)
        total_reservations = sum(row.reservation_count for row in field_points)
        total_income = sum((row.income_total for row in field_points), Decimal("0"))
        occupancy_rate = (
            (Decimal(occupied_fields) * Decimal("100")) / Decimal(total_fields)
            if total_fields > 0
            else Decimal("0")
        )

        return OccupancyMetricsResponse(
            period_window=AnalyticsPeriodWindow(period=period, start=start_at, end=end_at),
            filters=self._build_filters(
                campus_id=campus_id,
                field_id=field_id,
                sport_id=sport_id,
                status=status,
            ),
            summary=OccupancySummary(
                total_fields=total_fields,
                occupied_fields=occupied_fields,
                occupancy_rate=occupancy_rate,
                total_schedules=total_schedules,
                total_reservations=total_reservations,
                total_income=total_income,
            ),
            fields=field_points,
        )

    def get_top_occupancy(
        self,
        *,
        scope: str,
        period: str,
        target_date: Optional[date],
        start_date: Optional[date],
        end_date: Optional[date],
        limit: int,
        campus_id: Optional[int],
        field_id: Optional[int],
        sport_id: Optional[int],
        status: Optional[str],
    ) -> TopOccupancyResponse:
        self._apply_read_only_tx_guards()
        if limit < 1 or limit > 100:
            raise http_error(
                ANALYTICS_INVALID_LIMIT,
                detail="limit must be between 1 and 100",
            )

        start_at, end_at = self._resolve_period_window(
            period=period,
            target_date=target_date,
            start_date=start_date,
            end_date=end_date,
        )
        try:
            rows = fetch_top_occupancy_entities(
                self._db,
                start_at=start_at,
                end_at=end_at,
                scope=scope,
                limit=limit,
                campus_id=campus_id,
                field_id=field_id,
                sport_id=sport_id,
                status=status,
            )
        except (AnalyticsRepositoryError, ValueError) as exc:
            raise http_error(
                ANALYTICS_REPOSITORY_ERROR,
                detail="Unable to compute top occupancy ranking",
            ) from exc

        ranking_rows = [
            TopOccupancyEntity(
                scope=scope,
                entity_id=int(row["entity_id"]),
                entity_name=str(row["entity_name"]),
                campus_id=(
                    int(row["campus_id"]) if row.get("campus_id") is not None else None
                ),
                campus_name=(
                    str(row["campus_name"]) if row.get("campus_name") is not None else None
                ),
                reservation_count=int(row["reservation_count"]),
                income_total=self._normalize_decimal(row["income_total"]),
            )
            for row in rows
        ]

        return TopOccupancyResponse(
            period_window=AnalyticsPeriodWindow(period=period, start=start_at, end=end_at),
            scope=scope,
            limit=limit,
            filters=self._build_filters(
                campus_id=campus_id,
                field_id=field_id,
                sport_id=sport_id,
                status=status,
            ),
            rows=ranking_rows,
        )

    def get_peak_hours(
        self,
        *,
        scope: str,
        period: str,
        target_date: Optional[date],
        start_date: Optional[date],
        end_date: Optional[date],
        campus_id: Optional[int],
        field_id: Optional[int],
        sport_id: Optional[int],
        status: Optional[str],
        limit: int,
    ) -> PeakHoursResponse:
        self._apply_read_only_tx_guards()
        if limit < 1 or limit > 100:
            raise http_error(
                ANALYTICS_INVALID_LIMIT,
                detail="limit must be between 1 and 100",
            )

        if scope == "campus" and campus_id is None:
            raise http_error(
                ANALYTICS_INVALID_DATE_RANGE,
                detail="campus_id is required when scope='campus'",
            )
        if scope == "field" and field_id is None:
            raise http_error(
                ANALYTICS_INVALID_DATE_RANGE,
                detail="field_id is required when scope='field'",
            )
        if scope == "sport" and sport_id is None:
            raise http_error(
                ANALYTICS_INVALID_DATE_RANGE,
                detail="sport_id is required when scope='sport'",
            )

        start_at, end_at = self._resolve_period_window(
            period=period,
            target_date=target_date,
            start_date=start_date,
            end_date=end_date,
        )
        try:
            intersections = fetch_peak_hour_intersections(
                self._db,
                start_at=start_at,
                end_at=end_at,
                campus_id=campus_id,
                field_id=field_id,
                sport_id=sport_id,
                status=status,
            )
        except AnalyticsRepositoryError as exc:
            raise http_error(
                ANALYTICS_REPOSITORY_ERROR,
                detail="Unable to compute peak hours",
            ) from exc

        weekday_names = {
            1: "lunes",
            2: "martes",
            3: "miercoles",
            4: "jueves",
            5: "viernes",
            6: "sabado",
            7: "domingo",
        }

        hourly_count_map: Dict[int, int] = {hour: 0 for hour in range(24)}
        top_points: List[PeakIntersectionPoint] = []
        for row in intersections:
            isodow = int(row["isodow"])
            hour = int(row["hour"])
            reservation_count = int(row["reservation_count"])
            hourly_count_map[hour] = hourly_count_map.get(hour, 0) + reservation_count
            top_points.append(
                PeakIntersectionPoint(
                    weekday=weekday_names.get(isodow, str(isodow)),
                    hour=hour,
                    reservation_count=reservation_count,
                )
            )

        top_points.sort(key=lambda row: (-row.reservation_count, row.weekday, row.hour))
        hourly_distribution = [
            PeakHourPoint(hour=hour, reservation_count=hourly_count_map.get(hour, 0))
            for hour in range(24)
        ]

        return PeakHoursResponse(
            period_window=AnalyticsPeriodWindow(period=period, start=start_at, end=end_at),
            scope=scope,
            filters=self._build_filters(
                campus_id=campus_id,
                field_id=field_id,
                sport_id=sport_id,
                status=status,
            ),
            top_intersections=top_points[:limit],
            hourly_distribution=hourly_distribution,
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

    def _build_frequent_clients(
        self,
        rows: List[Dict[str, object]],
    ) -> List[FrequentClient]:
        clients: List[FrequentClient] = []
        for row in rows:
            clients.append(
                FrequentClient(
                    name=self._format_client_full_name(row.get("name"), row.get("lastname")),
                    email=row["email"],
                    phone=row["phone"],
                    image_url=row.get("image_url"),
                    city=row.get("city"),
                    district=row.get("district"),
                    rent_count=int(row["rent_count"]),
                )
            )
        return clients

    @staticmethod
    def _format_client_full_name(
        first_name: Optional[str],
        last_name: Optional[str],
    ) -> str:
        parts = []
        if first_name:
            parts.append(first_name.strip())
        if last_name:
            parts.append(last_name.strip())
        return " ".join(parts) if parts else ""

    def _build_last_seven_days_month_traffic_series(
        self,
        *,
        start_date: date,
        days: int,
        rows: List[Dict[str, object]],
    ) -> List[RentTrafficPoint]:
        weekday_totals: Dict[int, int] = {}
        for row in rows:
            period_start = _ensure_timezone(row["period_start"])
            weekday_index = period_start.date().weekday()
            weekday_totals[weekday_index] = weekday_totals.get(weekday_index, 0) + int(
                row["rent_count"]
            )

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
            weekday_index = day.weekday()
            weekday = weekday_names[weekday_index % len(weekday_names)]
            series.append(
                RentTrafficPoint(
                    record_date=day,
                    weekday=weekday,
                    rent_count=weekday_totals.get(weekday_index, 0),
                )
            )
        return series

    def _build_last_seven_days_daily_traffic_series(
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
            weekday_index = day.weekday()
            weekday = weekday_names[weekday_index % len(weekday_names)]
            series.append(
                RentTrafficPoint(
                    record_date=day,
                    weekday=weekday,
                    rent_count=lookup.get(day, 0),
                )
            )
        return series

    @staticmethod
    def _normalize_decimal(value: Decimal) -> Decimal:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value)) if value is not None else Decimal("0")


__all__ = ["AnalyticsService"]
