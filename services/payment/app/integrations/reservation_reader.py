"""Read-only access to reservation schema data for payment routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class RentContext:
    rent_id: int
    schedule_id: int
    field_id: Optional[int]
    user_id: Optional[int]
    amount: Optional[float]


def get_rent_context(db: Session, rent_id: int) -> Optional[RentContext]:
    query = text(
        """
        SELECT
            rent.id_rent AS rent_id,
            COALESCE(rent.id_schedule, picked.id_schedule) AS schedule_id,
            rent.mount AS amount,
            schedule.id_field AS field_id,
            schedule.id_user AS user_id
        FROM reservation.rent AS rent
        LEFT JOIN LATERAL (
            SELECT rs.id_schedule
            FROM reservation.rent_schedule AS rs
            WHERE rs.id_rent = rent.id_rent
            ORDER BY rs.is_primary DESC, rs.id_schedule ASC
            LIMIT 1
        ) AS picked ON true
        JOIN reservation.schedule AS schedule
            ON schedule.id_schedule = COALESCE(rent.id_schedule, picked.id_schedule)
        WHERE rent.id_rent = :rent_id
        """
    )
    row = db.execute(query, {"rent_id": rent_id}).mappings().first()
    if row is None:
        return None

    return RentContext(
        rent_id=int(row["rent_id"]),
        schedule_id=int(row["schedule_id"]),
        field_id=int(row["field_id"]) if row["field_id"] is not None else None,
        user_id=int(row["user_id"]) if row["user_id"] is not None else None,
        amount=float(row["amount"]) if row["amount"] is not None else None,
    )


__all__ = ["RentContext", "get_rent_context"]
