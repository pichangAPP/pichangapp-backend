"""Database helpers for analytics queries."""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Dict, Iterable, List, Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

ALLOWED_INTERVALS = {"day", "week", "month"}


class AnalyticsRepositoryError(RuntimeError):
    """Raised when the analytics repository cannot fulfill a request."""


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
) -> Decimal:
    """Return the total income for a campus in the given interval."""

    query = text(
        """
        SELECT COALESCE(SUM(rent.mount), 0) AS total_amount
        FROM reservation.rent AS rent
        JOIN reservation.schedule AS schedule ON schedule.id_schedule = rent.id_schedule
        JOIN booking.field AS field ON field.id_field = schedule.id_field
        WHERE rent.date_log >= :start_at
          AND rent.date_log < :end_at
          AND field.id_campus = :campus_id
          AND LOWER(rent.status) NOT IN ('available', 'pending', 'cancelled')
        """
    )

    try:
        result = db.execute(
            query,
            {
                "campus_id": campus_id,
                "start_at": start_at,
                "end_at": end_at,
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
) -> List[Dict[str, object]]:
    """Return the daily income entries for the specified campus and range."""

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
          AND LOWER(rent.status) NOT IN ('available', 'pending', 'cancelled')
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


__all__ = [
    "AnalyticsRepositoryError",
    "fetch_campus_daily_income",
    "fetch_campus_daily_rent_traffic",
    "fetch_campus_income_total",
    "fetch_campus_overview",
    "fetch_revenue_grouped_totals",
    "fetch_revenue_summary",
]
