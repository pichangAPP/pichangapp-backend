"""Database helpers for analytics queries."""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.integrations import auth_reader
ALLOWED_INTERVALS = {"day", "week", "month"}
ALLOWED_GROUP_BYS = {"day", "week", "month", "status", "campus", "field", "sport"}
ALLOWED_TOP_SCOPES = {"campus", "field", "sport"}
DEFAULT_CAMPUS_INCOME_STATUSES = ["reserved", "fullfilled"]
DEFAULT_ACTIVE_RESERVATION_STATUSES = ["reserved"]


class AnalyticsRepositoryError(RuntimeError):
    """Raised when the analytics repository cannot fulfill a request."""


def _normalize_status_filters(
    *,
    status: Optional[str],
    statuses: Optional[Sequence[str]],
) -> Optional[List[str]]:
    """Normalize status filters into a lowercase unique list."""

    normalized: List[str] = []

    if statuses:
        for value in statuses:
            candidate = (value or "").strip().lower()
            if candidate and candidate not in normalized:
                normalized.append(candidate)

    single = (status or "").strip().lower()
    if single and single not in normalized:
        normalized.append(single)

    return normalized or None


def _execute_grouped_query(
    db: Session,
    *,
    start_at: datetime,
    end_at: datetime,
    interval: str,
    status: Optional[str],
) -> Iterable[Dict[str, object]]:
    if interval not in ALLOWED_INTERVALS:
        raise ValueError(f"Unsupported interval '{interval}'")

    query = text(
        f"""
        SELECT
            campus.id_campus AS campus_id,
            campus.name AS campus_name,
            date_trunc('{interval}', rent.date_log) AS period_start,
            SUM(rent.mount) AS total_amount,
            COUNT(rent.id_rent) AS rent_count
        FROM reservation.rent AS rent
        JOIN reservation.schedule AS schedule ON schedule.id_schedule = rent.id_schedule
        JOIN booking.field AS field ON field.id_field = schedule.id_field
        JOIN booking.campus AS campus ON campus.id_campus = field.id_campus
        WHERE rent.date_log >= :start_at
          AND rent.date_log < :end_at
          AND (:status IS NULL OR rent.status = :status)
        GROUP BY campus.id_campus, campus.name, period_start
        ORDER BY campus.name ASC, period_start ASC
        """
    )

    try:
        result = db.execute(
            query,
            {
                "start_at": start_at,
                "end_at": end_at,
                "status": status,
            },
        )
    except SQLAlchemyError as exc:  # pragma: no cover - defensive programming
        raise AnalyticsRepositoryError(str(exc)) from exc

    for row in result:
        yield {
            "campus_id": row.campus_id,
            "campus_name": row.campus_name,
            "period_start": row.period_start,
            "total_amount": row.total_amount,
            "rent_count": row.rent_count,
        }


def fetch_revenue_grouped_totals(
    db: Session,
    *,
    start_at: datetime,
    end_at: datetime,
    interval: str,
    status: Optional[str] = None,
) -> List[Dict[str, object]]:
    """Return revenue totals grouped by the requested interval."""

    rows = list(
        _execute_grouped_query(
            db,
            start_at=start_at,
            end_at=end_at,
            interval=interval,
            status=status,
        )
    )

    # Normalize total_amount values to Decimal for consistent downstream usage.
    normalized: List[Dict[str, object]] = []
    for row in rows:
        amount = row["total_amount"]
        if amount is None:
            normalized_amount = Decimal("0")
        elif isinstance(amount, Decimal):
            normalized_amount = amount
        else:
            normalized_amount = Decimal(str(amount))
        normalized.append(
            {
                "campus_id": row["campus_id"],
                "campus_name": row["campus_name"],
                "period_start": row["period_start"],
                "total_amount": normalized_amount,
                "rent_count": int(row["rent_count"]),
            }
        )
    return normalized


def fetch_revenue_summary(
    db: Session,
    *,
    start_at: datetime,
    end_at: datetime,
    status: Optional[str] = None,
) -> Dict[str, List[Dict[str, object]]]:
    """Return revenue totals grouped by day, week and month."""

    return {
        "daily": fetch_revenue_grouped_totals(
            db,
            start_at=start_at,
            end_at=end_at,
            interval="day",
            status=status,
        ),
        "weekly": fetch_revenue_grouped_totals(
            db,
            start_at=start_at,
            end_at=end_at,
            interval="week",
            status=status,
        ),
        "monthly": fetch_revenue_grouped_totals(
            db,
            start_at=start_at,
            end_at=end_at,
            interval="month",
            status=status,
        ),
    }


def fetch_campus_income_total(
    db: Session,
    *,
    campus_id: int,
    start_at: datetime,
    end_at: datetime,
    status: Optional[str] = None,
    statuses: Optional[Sequence[str]] = None,
) -> Decimal:
    """Return the total income for a campus in the given interval."""

    status_filters = _normalize_status_filters(status=status, statuses=statuses)
    if not status_filters:
        status_filters = DEFAULT_CAMPUS_INCOME_STATUSES

    query = text(
        """
        SELECT COALESCE(SUM(rent.mount), 0) AS total_amount
        FROM reservation.rent AS rent
        JOIN reservation.schedule AS schedule ON schedule.id_schedule = rent.id_schedule
        JOIN booking.field AS field ON field.id_field = schedule.id_field
        WHERE rent.date_log >= :start_at
          AND rent.date_log < :end_at
          AND field.id_campus = :campus_id
          AND LOWER(rent.status) = ANY(:status_filters)
        """
    )

    try:
        result = db.execute(
            query,
            {
                "campus_id": campus_id,
                "start_at": start_at,
                "end_at": end_at,
                "status_filters": status_filters,
            },
        )
    except SQLAlchemyError as exc:  # pragma: no cover - defensive programming
        raise AnalyticsRepositoryError(str(exc)) from exc

    amount = result.scalar()
    if amount is None:
        return Decimal("0")
    if isinstance(amount, Decimal):
        return amount
    return Decimal(str(amount))


def fetch_campus_daily_income(
    db: Session,
    *,
    campus_id: int,
    start_at: datetime,
    end_at: datetime,
    status: Optional[str] = None,
    statuses: Optional[Sequence[str]] = None,
) -> List[Dict[str, object]]:
    """Return the daily income entries for the specified campus and range."""

    status_filters = _normalize_status_filters(status=status, statuses=statuses)
    if not status_filters:
        status_filters = DEFAULT_CAMPUS_INCOME_STATUSES

    query = text(
        """
        SELECT
            date_trunc('day', rent.date_log) AS period_start,
            SUM(rent.mount) AS total_amount
        FROM reservation.rent AS rent
        JOIN reservation.schedule AS schedule ON schedule.id_schedule = rent.id_schedule
        JOIN booking.field AS field ON field.id_field = schedule.id_field
        WHERE rent.date_log >= :start_at
          AND rent.date_log < :end_at
          AND field.id_campus = :campus_id
          AND LOWER(rent.status) = ANY(:status_filters)
        GROUP BY period_start
        ORDER BY period_start ASC
        """
    )

    try:
        result = db.execute(
            query,
            {
                "campus_id": campus_id,
                "start_at": start_at,
                "end_at": end_at,
                "status_filters": status_filters,
            },
        )
    except SQLAlchemyError as exc:  # pragma: no cover - defensive programming
        raise AnalyticsRepositoryError(str(exc)) from exc

    entries: List[Dict[str, object]] = []
    for row in result:
        amount = row.total_amount
        if amount is None:
            normalized_amount = Decimal("0")
        elif isinstance(amount, Decimal):
            normalized_amount = amount
        else:
            normalized_amount = Decimal(str(amount))
        entries.append(
            {
                "period_start": row.period_start,
                "total_amount": normalized_amount,
            }
        )
    return entries


def fetch_campus_daily_rent_traffic(
    db: Session,
    *,
    campus_id: int,
    start_at: datetime,
    end_at: datetime,
) -> List[Dict[str, object]]:
    """Return the number of rents per day for the campus in the given range."""
    status_filters = DEFAULT_CAMPUS_INCOME_STATUSES

    query = text(
        """
        SELECT
            date_trunc('day', rent.date_log) AS period_start,
            COUNT(rent.id_rent) AS rent_count
        FROM reservation.rent AS rent
        JOIN reservation.schedule AS schedule ON schedule.id_schedule = rent.id_schedule
        JOIN booking.field AS field ON field.id_field = schedule.id_field
        WHERE rent.date_log >= :start_at
          AND rent.date_log < :end_at
          AND field.id_campus = :campus_id
          AND LOWER(rent.status) = ANY(:status_filters)
        GROUP BY period_start
        ORDER BY period_start ASC
        """
    )

    try:
        result = db.execute(
            query,
            {
                "campus_id": campus_id,
                "start_at": start_at,
                "end_at": end_at,
                "status_filters": status_filters,
            },
        )
    except SQLAlchemyError as exc:  # pragma: no cover - defensive programming
        raise AnalyticsRepositoryError(str(exc)) from exc

    entries: List[Dict[str, object]] = []
    for row in result:
        entries.append(
            {
                "period_start": row.period_start,
                "rent_count": int(row.rent_count),
            }
        )
    return entries


def fetch_campus_overview(
    db: Session,
    *,
    campus_id: int,
) -> Optional[Dict[str, object]]:
    """Return basic campus information along with field availability."""

    query = text(
        """
        SELECT
            campus.id_campus AS campus_id,
            campus.name AS campus_name,
            COUNT(field.id_field) AS total_fields,
            CASE
                WHEN COUNT(field.id_field) = 0 THEN 0  -- No fields at all
                WHEN SUM(CASE WHEN LOWER(field.status) != 'active' THEN 1 ELSE 0 END) = 0
                    THEN COUNT(field.id_field)  -- All are available
                ELSE
                    SUM(CASE WHEN LOWER(field.status) = 'active' THEN 1 ELSE 0 END)
            END AS available_fields
        FROM booking.campus AS campus
        LEFT JOIN booking.field AS field ON field.id_campus = campus.id_campus
        WHERE campus.id_campus = :campus_id
        GROUP BY campus.id_campus, campus.name
        """
    )


    try:
        result = db.execute(query, {"campus_id": campus_id})
    except SQLAlchemyError as exc:  # pragma: no cover - defensive programming
        raise AnalyticsRepositoryError(str(exc)) from exc

    row = result.first()
    if row is None:
        return None

    return {
        "campus_id": row.campus_id,
        "campus_name": row.campus_name,
        "total_fields": int(row.total_fields or 0),
        "available_fields": int(row.available_fields or 0),
    }


def fetch_campus_top_clients(
    db: Session,
    *,
    campus_id: int,
    limit: int,
) -> List[Dict[str, object]]:
    """Return the most frequent clients for the specified campus."""
    status_filters = DEFAULT_CAMPUS_INCOME_STATUSES

    query = text(
        """
        SELECT
            schedule.id_user AS id_user,
            COUNT(rent.id_rent) AS rent_count
        FROM reservation.rent AS rent
        JOIN reservation.schedule AS schedule ON schedule.id_schedule = rent.id_schedule
        JOIN booking.field AS field ON field.id_field = schedule.id_field
        WHERE field.id_campus = :campus_id
          AND LOWER(rent.status) = ANY(:status_filters)
        GROUP BY
            schedule.id_user
        """
    )

    try:
        result = db.execute(
            query,
            {"campus_id": campus_id, "status_filters": status_filters},
        )
    except SQLAlchemyError as exc:  # pragma: no cover - defensive programming
        raise AnalyticsRepositoryError(str(exc)) from exc

    rows = result.mappings().all()
    if not rows:
        return []

    rent_counts = {
        row["id_user"]: int(row["rent_count"]) for row in rows if row["id_user"] is not None
    }
    try:
        user_profiles = auth_reader.get_user_summaries(db, rent_counts.keys())
    except auth_reader.AuthReaderError as exc:
        raise AnalyticsRepositoryError(str(exc)) from exc

    entries: List[Dict[str, object]] = []
    for user_id, rent_count in rent_counts.items():
        profile = user_profiles.get(user_id)
        if profile is None:
            continue
        entries.append(
            {
                "id_user": user_id,
                "name": profile.get("name"),
                "lastname": profile.get("lastname"),
                "email": profile.get("email"),
                "phone": profile.get("phone"),
                "image_url": profile.get("imageurl"),
                "city": profile.get("city"),
                "district": profile.get("district"),
                "rent_count": rent_count,
            }
        )

    entries.sort(
        key=lambda row: (
            -row["rent_count"],
            (row.get("name") or "").lower(),
            (row.get("lastname") or "").lower(),
        )
    )
    return entries[:limit]


def fetch_campus_top_fields(
    db: Session,
    *,
    campus_id: int,
    start_at: datetime,
    end_at: datetime,
    limit: int,
) -> List[Dict[str, object]]:
    status_filters = DEFAULT_CAMPUS_INCOME_STATUSES

    query = text(
        """
        SELECT
            field.id_field,
            field.field_name AS field_name,
            COUNT(rent.id_rent) AS usage_count
        FROM reservation.rent AS rent
        JOIN reservation.schedule AS schedule ON schedule.id_schedule = rent.id_schedule
        JOIN booking.field AS field ON field.id_field = schedule.id_field
        WHERE field.id_campus = :campus_id
          AND rent.date_log >= :start_at
          AND rent.date_log < :end_at
          AND LOWER(rent.status) = ANY(:status_filters)
        GROUP BY field.id_field, field.field_name
        ORDER BY usage_count DESC, field.field_name ASC
        LIMIT :limit
        """
    )
    try:
        result = db.execute(
            query,
            {
                "campus_id": campus_id,
                "start_at": start_at,
                "end_at": end_at,
                "status_filters": status_filters,
                "limit": limit,
            },
        )
    except SQLAlchemyError as exc:
        raise AnalyticsRepositoryError(str(exc)) from exc

    entries: List[Dict[str, object]] = []
    for row in result:
        entries.append(
            {
                "field_id": row.id_field,
                "field_name": row.field_name,
                "usage_count": int(row.usage_count),
            }
        )
    return entries


def fetch_campus_active_reservations(
    db: Session,
    *,
    campus_id: int,
    start_at: datetime,
    end_at: datetime,
    field_name: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, object]]:
    """Return active reservations for a campus in the requested time window."""
    active_status_filters = DEFAULT_ACTIVE_RESERVATION_STATUSES

    query = text(
        """
        SELECT
            rent.id_rent AS rent_id,
            rent.status AS rent_status,
            schedule.start_time AS start_time,
            schedule.end_time AS end_time,
            field.id_field AS field_id,
            field.field_name AS field_name,
            schedule.id_user AS user_id
        FROM reservation.rent AS rent
        JOIN reservation.schedule AS schedule ON schedule.id_schedule = rent.id_schedule
        JOIN booking.field AS field ON field.id_field = schedule.id_field
        WHERE field.id_campus = :campus_id
          AND schedule.start_time >= :start_at
          AND schedule.start_time < :end_at
          AND LOWER(rent.status) = ANY(:active_status_filters)
          AND (
              :field_name IS NULL
              OR LOWER(field.field_name) LIKE LOWER(:field_name_pattern)
          )
        ORDER BY schedule.start_time ASC, field.field_name ASC
        LIMIT :limit
        """
    )
    try:
        result = db.execute(
            query,
            {
                "campus_id": campus_id,
                "start_at": start_at,
                "end_at": end_at,
                "active_status_filters": active_status_filters,
                "field_name": field_name,
                "field_name_pattern": f"%{field_name.strip()}%" if field_name else None,
                "limit": int(limit),
            },
        )
    except SQLAlchemyError as exc:
        raise AnalyticsRepositoryError(str(exc)) from exc

    entries: List[Dict[str, object]] = []
    for row in result:
        entries.append(
            {
                "rent_id": int(row.rent_id),
                "rent_status": row.rent_status,
                "start_time": row.start_time,
                "end_time": row.end_time,
                "field_id": int(row.field_id),
                "field_name": row.field_name,
                "user_id": int(row.user_id) if row.user_id is not None else None,
            }
        )
    return entries


def _to_decimal(value: object) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def fetch_grouped_rent_metrics(
    db: Session,
    *,
    start_at: datetime,
    end_at: datetime,
    group_by: str,
    campus_id: Optional[int] = None,
    field_id: Optional[int] = None,
    sport_id: Optional[int] = None,
    status: Optional[str] = None,
) -> List[Dict[str, object]]:
    """Return reusable grouped reservation/income metrics with common filters."""

    if group_by not in ALLOWED_GROUP_BYS:
        raise ValueError(f"Unsupported group_by '{group_by}'")

    if group_by == "day":
        key_expr = "to_char(date_trunc('day', rent.date_log), 'YYYY-MM-DD')"
        label_expr = key_expr
        group_expr = "date_trunc('day', rent.date_log)"
        order_expr = group_expr
    elif group_by == "week":
        key_expr = "to_char(date_trunc('week', rent.date_log), 'IYYY-IW')"
        label_expr = key_expr
        group_expr = "date_trunc('week', rent.date_log)"
        order_expr = group_expr
    elif group_by == "month":
        key_expr = "to_char(date_trunc('month', rent.date_log), 'YYYY-MM')"
        label_expr = key_expr
        group_expr = "date_trunc('month', rent.date_log)"
        order_expr = group_expr
    elif group_by == "status":
        key_expr = "lower(rent.status)"
        label_expr = "initcap(replace(lower(rent.status), '_', ' '))"
        group_expr = "lower(rent.status)"
        order_expr = "lower(rent.status)"
    elif group_by == "campus":
        key_expr = "campus.id_campus::text"
        label_expr = "campus.name"
        group_expr = "campus.id_campus, campus.name"
        order_expr = "campus.name"
    elif group_by == "field":
        key_expr = "field.id_field::text"
        label_expr = "field.field_name"
        group_expr = "field.id_field, field.field_name"
        order_expr = "field.field_name"
    else:  # sport
        key_expr = "sport.id_sport::text"
        label_expr = "sport.sport_name"
        group_expr = "sport.id_sport, sport.sport_name"
        order_expr = "sport.sport_name"

    query = text(
        f"""
        SELECT
            {key_expr} AS group_key,
            {label_expr} AS group_label,
            COUNT(rent.id_rent) AS reservation_count,
            COALESCE(SUM(rent.mount), 0) AS income_total
        FROM reservation.rent AS rent
        JOIN reservation.schedule AS schedule ON schedule.id_schedule = rent.id_schedule
        JOIN booking.field AS field ON field.id_field = schedule.id_field
        JOIN booking.campus AS campus ON campus.id_campus = field.id_campus
        JOIN booking.sports AS sport ON sport.id_sport = field.id_sport
        WHERE rent.date_log >= :start_at
          AND rent.date_log < :end_at
          AND (:campus_id IS NULL OR campus.id_campus = :campus_id)
          AND (:field_id IS NULL OR field.id_field = :field_id)
          AND (:sport_id IS NULL OR sport.id_sport = :sport_id)
          AND (:status IS NULL OR LOWER(rent.status) = LOWER(:status))
        GROUP BY {group_expr}
        ORDER BY {order_expr} ASC
        """
    )
    try:
        result = db.execute(
            query,
            {
                "start_at": start_at,
                "end_at": end_at,
                "campus_id": campus_id,
                "field_id": field_id,
                "sport_id": sport_id,
                "status": status,
            },
        )
    except SQLAlchemyError as exc:
        raise AnalyticsRepositoryError(str(exc)) from exc

    rows: List[Dict[str, object]] = []
    for row in result:
        rows.append(
            {
                "group_key": str(row.group_key),
                "group_label": str(row.group_label),
                "reservation_count": int(row.reservation_count),
                "income_total": _to_decimal(row.income_total),
            }
        )
    return rows


def fetch_field_occupancy_snapshot(
    db: Session,
    *,
    start_at: datetime,
    end_at: datetime,
    campus_id: Optional[int] = None,
    field_id: Optional[int] = None,
    sport_id: Optional[int] = None,
    status: Optional[str] = None,
) -> List[Dict[str, object]]:
    """Return occupancy/income/reservation metrics per field for the time window."""
    status_filters = _normalize_status_filters(status=status, statuses=None)
    if not status_filters:
        status_filters = DEFAULT_CAMPUS_INCOME_STATUSES
    active_status_filters = DEFAULT_ACTIVE_RESERVATION_STATUSES

    query = text(
        """
        SELECT
            campus.id_campus AS campus_id,
            campus.name AS campus_name,
            field.id_field AS field_id,
            field.field_name AS field_name,
            field.status AS field_status,
            sport.id_sport AS sport_id,
            sport.sport_name AS sport_name,
            COUNT(DISTINCT schedule.id_schedule) AS total_schedules,
            COUNT(DISTINCT rent.id_rent) FILTER (
                WHERE LOWER(rent.status) = ANY(:status_filters)
            ) AS reservation_count,
            COALESCE(
                SUM(rent.mount) FILTER (
                    WHERE LOWER(rent.status) = ANY(:status_filters)
                ),
                0
            ) AS income_total,
            COUNT(DISTINCT rent.id_rent) FILTER (
                WHERE (
                    (:status IS NOT NULL AND LOWER(rent.status) = LOWER(:status))
                    OR (
                        :status IS NULL
                        AND LOWER(rent.status) = ANY(:active_status_filters)
                    )
                )
            ) AS active_reservation_count
        FROM booking.field AS field
        JOIN booking.campus AS campus ON campus.id_campus = field.id_campus
        JOIN booking.sports AS sport ON sport.id_sport = field.id_sport
        LEFT JOIN reservation.schedule AS schedule
            ON schedule.id_field = field.id_field
           AND schedule.start_time >= :start_at
           AND schedule.start_time < :end_at
        LEFT JOIN reservation.rent AS rent ON rent.id_schedule = schedule.id_schedule
        WHERE (:campus_id IS NULL OR campus.id_campus = :campus_id)
          AND (:field_id IS NULL OR field.id_field = :field_id)
          AND (:sport_id IS NULL OR sport.id_sport = :sport_id)
        GROUP BY
            campus.id_campus,
            campus.name,
            field.id_field,
            field.field_name,
            field.status,
            sport.id_sport,
            sport.sport_name
        ORDER BY campus.name ASC, field.field_name ASC
        """
    )
    try:
        result = db.execute(
            query,
            {
                "start_at": start_at,
                "end_at": end_at,
                "campus_id": campus_id,
                "field_id": field_id,
                "sport_id": sport_id,
                "status_filters": status_filters,
                "active_status_filters": active_status_filters,
            },
        )
    except SQLAlchemyError as exc:
        raise AnalyticsRepositoryError(str(exc)) from exc

    rows: List[Dict[str, object]] = []
    for row in result:
        rows.append(
            {
                "campus_id": int(row.campus_id),
                "campus_name": str(row.campus_name),
                "field_id": int(row.field_id),
                "field_name": str(row.field_name),
                "field_status": str(row.field_status or ""),
                "sport_id": int(row.sport_id),
                "sport_name": str(row.sport_name),
                "total_schedules": int(row.total_schedules or 0),
                "reservation_count": int(row.reservation_count or 0),
                "income_total": _to_decimal(row.income_total),
                "active_reservation_count": int(row.active_reservation_count or 0),
            }
        )
    return rows


def fetch_top_occupancy_entities(
    db: Session,
    *,
    start_at: datetime,
    end_at: datetime,
    scope: str,
    limit: int,
    campus_id: Optional[int] = None,
    field_id: Optional[int] = None,
    sport_id: Optional[int] = None,
    status: Optional[str] = None,
) -> List[Dict[str, object]]:
    """Return top entities by reservation count and income for the selected scope."""
    status_filters = _normalize_status_filters(status=status, statuses=None)
    if not status_filters:
        status_filters = DEFAULT_CAMPUS_INCOME_STATUSES

    if scope not in ALLOWED_TOP_SCOPES:
        raise ValueError(f"Unsupported scope '{scope}'")

    if scope == "campus":
        entity_id_expr = "campus.id_campus"
        entity_name_expr = "campus.name"
        group_expr = "campus.id_campus, campus.name"
        campus_select = "NULL::bigint AS campus_id, NULL::text AS campus_name"
    elif scope == "field":
        entity_id_expr = "field.id_field"
        entity_name_expr = "field.field_name"
        group_expr = "field.id_field, field.field_name, campus.id_campus, campus.name"
        campus_select = "campus.id_campus AS campus_id, campus.name AS campus_name"
    else:  # sport
        entity_id_expr = "sport.id_sport"
        entity_name_expr = "sport.sport_name"
        group_expr = "sport.id_sport, sport.sport_name"
        campus_select = "NULL::bigint AS campus_id, NULL::text AS campus_name"

    query = text(
        f"""
        SELECT
            {entity_id_expr} AS entity_id,
            {entity_name_expr} AS entity_name,
            {campus_select},
            COUNT(rent.id_rent) AS reservation_count,
            COALESCE(SUM(rent.mount), 0) AS income_total
        FROM reservation.rent AS rent
        JOIN reservation.schedule AS schedule ON schedule.id_schedule = rent.id_schedule
        JOIN booking.field AS field ON field.id_field = schedule.id_field
        JOIN booking.campus AS campus ON campus.id_campus = field.id_campus
        JOIN booking.sports AS sport ON sport.id_sport = field.id_sport
        WHERE rent.date_log >= :start_at
          AND rent.date_log < :end_at
          AND (:campus_id IS NULL OR campus.id_campus = :campus_id)
          AND (:field_id IS NULL OR field.id_field = :field_id)
          AND (:sport_id IS NULL OR sport.id_sport = :sport_id)
          AND LOWER(rent.status) = ANY(:status_filters)
        GROUP BY {group_expr}
        ORDER BY reservation_count DESC, income_total DESC, entity_name ASC
        LIMIT :limit
        """
    )
    try:
        result = db.execute(
            query,
            {
                "start_at": start_at,
                "end_at": end_at,
                "campus_id": campus_id,
                "field_id": field_id,
                "sport_id": sport_id,
                "status_filters": status_filters,
                "limit": int(limit),
            },
        )
    except SQLAlchemyError as exc:
        raise AnalyticsRepositoryError(str(exc)) from exc

    rows: List[Dict[str, object]] = []
    for row in result:
        rows.append(
            {
                "entity_id": int(row.entity_id),
                "entity_name": str(row.entity_name),
                "campus_id": int(row.campus_id) if row.campus_id is not None else None,
                "campus_name": str(row.campus_name) if row.campus_name is not None else None,
                "reservation_count": int(row.reservation_count or 0),
                "income_total": _to_decimal(row.income_total),
            }
        )
    return rows


def fetch_peak_hour_intersections(
    db: Session,
    *,
    start_at: datetime,
    end_at: datetime,
    campus_id: Optional[int] = None,
    field_id: Optional[int] = None,
    sport_id: Optional[int] = None,
    status: Optional[str] = None,
) -> List[Dict[str, object]]:
    """Return reservation counts grouped by (weekday, hour)."""
    status_filters = _normalize_status_filters(status=status, statuses=None)
    if not status_filters:
        status_filters = DEFAULT_CAMPUS_INCOME_STATUSES

    query = text(
        """
        SELECT
            EXTRACT(ISODOW FROM schedule.start_time)::int AS isodow,
            EXTRACT(HOUR FROM schedule.start_time)::int AS hour,
            COUNT(rent.id_rent) AS reservation_count
        FROM reservation.rent AS rent
        JOIN reservation.schedule AS schedule ON schedule.id_schedule = rent.id_schedule
        JOIN booking.field AS field ON field.id_field = schedule.id_field
        JOIN booking.campus AS campus ON campus.id_campus = field.id_campus
        JOIN booking.sports AS sport ON sport.id_sport = field.id_sport
        WHERE schedule.start_time >= :start_at
          AND schedule.start_time < :end_at
          AND (:campus_id IS NULL OR campus.id_campus = :campus_id)
          AND (:field_id IS NULL OR field.id_field = :field_id)
          AND (:sport_id IS NULL OR sport.id_sport = :sport_id)
          AND LOWER(rent.status) = ANY(:status_filters)
        GROUP BY isodow, hour
        ORDER BY reservation_count DESC, isodow ASC, hour ASC
        """
    )
    try:
        result = db.execute(
            query,
            {
                "start_at": start_at,
                "end_at": end_at,
                "campus_id": campus_id,
                "field_id": field_id,
                "sport_id": sport_id,
                "status_filters": status_filters,
            },
        )
    except SQLAlchemyError as exc:
        raise AnalyticsRepositoryError(str(exc)) from exc

    rows: List[Dict[str, object]] = []
    for row in result:
        rows.append(
            {
                "isodow": int(row.isodow),
                "hour": int(row.hour),
                "reservation_count": int(row.reservation_count or 0),
            }
        )
    return rows


__all__ = [
    "AnalyticsRepositoryError",
    "fetch_campus_daily_income",
    "fetch_campus_daily_rent_traffic",
    "fetch_campus_income_total",
    "fetch_campus_overview",
    "fetch_campus_active_reservations",
    "fetch_campus_top_clients",
    "fetch_campus_top_fields",
    "fetch_grouped_rent_metrics",
    "fetch_field_occupancy_snapshot",
    "fetch_top_occupancy_entities",
    "fetch_peak_hour_intersections",
    "fetch_revenue_grouped_totals",
    "fetch_revenue_summary",
]
