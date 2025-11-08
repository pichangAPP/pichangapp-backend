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
    currency: Optional[str],
    status: Optional[str],
) -> Iterable[Dict[str, object]]:
    if interval not in ALLOWED_INTERVALS:
        raise ValueError(f"Unsupported interval '{interval}'")

    query = text(
        f"""
        SELECT
            date_trunc('{interval}', paid_at) AS period_start,
            currency,
            SUM(amount) AS total_amount
        FROM payment.payment
        WHERE paid_at >= :start_at
          AND paid_at < :end_at
          AND (:status IS NULL OR status = :status)
          AND (:currency IS NULL OR currency = :currency)
        GROUP BY period_start, currency
        ORDER BY period_start ASC, currency ASC
        """
    )

    try:
        result = db.execute(
            query,
            {
                "start_at": start_at,
                "end_at": end_at,
                "status": status,
                "currency": currency,
            },
        )
    except SQLAlchemyError as exc:  # pragma: no cover - defensive programming
        raise AnalyticsRepositoryError(str(exc)) from exc

    for row in result:
        yield {
            "period_start": row.period_start,
            "currency": row.currency,
            "total_amount": row.total_amount,
        }


def fetch_revenue_grouped_totals(
    db: Session,
    *,
    start_at: datetime,
    end_at: datetime,
    interval: str,
    currency: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, object]]:
    """Return revenue totals grouped by the requested interval."""

    rows = list(
        _execute_grouped_query(
            db,
            start_at=start_at,
            end_at=end_at,
            interval=interval,
            currency=currency,
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
                "period_start": row["period_start"],
                "currency": row["currency"],
                "total_amount": normalized_amount,
            }
        )
    return normalized


def fetch_revenue_summary(
    db: Session,
    *,
    start_at: datetime,
    end_at: datetime,
    currency: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, List[Dict[str, object]]]:
    """Return revenue totals grouped by day, week and month."""

    return {
        "daily": fetch_revenue_grouped_totals(
            db,
            start_at=start_at,
            end_at=end_at,
            interval="day",
            currency=currency,
            status=status,
        ),
        "weekly": fetch_revenue_grouped_totals(
            db,
            start_at=start_at,
            end_at=end_at,
            interval="week",
            currency=currency,
            status=status,
        ),
        "monthly": fetch_revenue_grouped_totals(
            db,
            start_at=start_at,
            end_at=end_at,
            interval="month",
            currency=currency,
            status=status,
        ),
    }


__all__ = [
    "AnalyticsRepositoryError",
    "fetch_revenue_grouped_totals",
    "fetch_revenue_summary",
]
