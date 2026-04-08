"""Read-only access to booking schema data for payment routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class PaymentDestination:
    field_id: int
    campus_id: int
    campus_name: str
    manager_id: Optional[int]
    business_name: str
    business_phone: Optional[str]


def get_payment_destination(db: Session, field_id: int) -> Optional[PaymentDestination]:
    query = text(
        """
        SELECT
            field.id_field AS field_id,
            campus.id_campus AS campus_id,
            campus.name AS campus_name,
            campus.id_manager AS manager_id,
            business.name AS business_name,
            business.phone_contact AS business_phone
        FROM booking.field AS field
        JOIN booking.campus AS campus ON campus.id_campus = field.id_campus
        JOIN booking.business AS business ON business.id_business = campus.id_business
        WHERE field.id_field = :field_id
        """
    )
    row = db.execute(query, {"field_id": field_id}).mappings().first()
    if row is None:
        return None

    return PaymentDestination(
        field_id=int(row["field_id"]),
        campus_id=int(row["campus_id"]),
        campus_name=str(row["campus_name"]),
        manager_id=int(row["manager_id"]) if row["manager_id"] is not None else None,
        business_name=str(row["business_name"]),
        business_phone=row["business_phone"],
    )


__all__ = ["PaymentDestination", "get_payment_destination"]
