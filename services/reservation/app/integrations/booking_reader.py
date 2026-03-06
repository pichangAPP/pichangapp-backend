"""Read/write access to booking schema data without ORM models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.schemas.schedule import FieldSummary


_FIELD_COLUMNS = """
    id_field,
    field_name,
    capacity,
    surface,
    measurement,
    price_per_hour,
    status,
    open_time,
    close_time,
    minutes_wait,
    id_sport,
    id_campus
"""


@dataclass(frozen=True)
class CampusSummary:
    id_campus: int
    name: str
    address: str
    district: str
    id_manager: Optional[int]
    contact_email: Optional[str]
    contact_phone: Optional[str]


def get_field_summary(db: Session, field_id: int) -> Optional[FieldSummary]:
    query = text(
        f"""
        SELECT {_FIELD_COLUMNS}
        FROM booking.field
        WHERE id_field = :field_id
        """
    )
    row = db.execute(query, {"field_id": field_id}).mappings().first()
    if row is None:
        return None
    return FieldSummary(**row)


def get_field_summaries(
    db: Session,
    field_ids: Iterable[int],
) -> dict[int, FieldSummary]:
    unique_ids = {field_id for field_id in field_ids if field_id is not None}
    if not unique_ids:
        return {}

    query = text(
        f"""
        SELECT {_FIELD_COLUMNS}
        FROM booking.field
        WHERE id_field IN :field_ids
        """
    ).bindparams(bindparam("field_ids", expanding=True))

    rows = db.execute(query, {"field_ids": list(unique_ids)}).mappings().all()
    return {row["id_field"]: FieldSummary(**row) for row in rows}


def get_field_ids_by_campus(db: Session, campus_id: int) -> list[int]:
    query = text(
        """
        SELECT id_field
        FROM booking.field
        WHERE id_campus = :campus_id
        """
    )
    return list(db.execute(query, {"campus_id": campus_id}).scalars().all())


def get_campus_summary(db: Session, campus_id: int) -> Optional[CampusSummary]:
    query = text(
        """
        SELECT
            campus.id_campus,
            campus.name,
            campus.address,
            campus.district,
            campus.id_manager,
            business.email_contact,
            business.phone_contact
        FROM booking.campus AS campus
        JOIN booking.business AS business
            ON business.id_business = campus.id_business
        WHERE id_campus = :campus_id
        """
    )
    row = db.execute(query, {"campus_id": campus_id}).mappings().first()
    if row is None:
        return None
    return CampusSummary(**row)


def update_field_status(db: Session, field_id: int, status: str) -> bool:
    query = text(
        """
        UPDATE booking.field
        SET status = :status
        WHERE id_field = :field_id
        """
    )
    result = db.execute(query, {"status": status, "field_id": field_id})
    db.commit()
    return bool(result.rowcount)


__all__ = [
    "CampusSummary",
    "get_campus_summary",
    "get_field_ids_by_campus",
    "get_field_summary",
    "get_field_summaries",
    "update_field_status",
]
