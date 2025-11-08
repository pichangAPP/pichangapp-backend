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


__all__ = [
    "AnalyticsRepositoryError",
    "fetch_revenue_grouped_totals",
    "fetch_revenue_summary",
]
