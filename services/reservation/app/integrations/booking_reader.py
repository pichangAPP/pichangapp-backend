"""Read/write access to booking schema data without ORM models."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Optional, Tuple

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY, BIGINT
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
    email_contact: Optional[str]
    phone_contact: Optional[str]


@dataclass(frozen=True)
class FieldCombinationForReservation:
    id_combination: int
    id_campus: int
    status: str
    price_per_hour: Decimal
    member_field_ids: Tuple[int, ...]


def get_field_combination_for_reservation(
    db: Session,
    combination_id: int,
    *,
    active_only: bool = True,
) -> Optional[FieldCombinationForReservation]:
    status_clause = "AND c.status = 'active'" if active_only else ""
    query = text(
        f"""
        SELECT
            c.id_combination,
            c.id_campus,
            c.status,
            c.price_per_hour,
            array_agg(m.id_field ORDER BY m.sort_order, m.id_field) AS field_ids
        FROM booking.field_combination c
        JOIN booking.field_combination_member m ON m.id_combination = c.id_combination
        WHERE c.id_combination = :cid
        {status_clause}
        GROUP BY c.id_combination, c.id_campus, c.status, c.price_per_hour
        """
    )
    row = db.execute(query, {"cid": combination_id}).mappings().first()
    if row is None:
        return None
    raw_ids = row["field_ids"]
    if raw_ids is None:
        return None
    field_ids = tuple(int(x) for x in raw_ids)
    return FieldCombinationForReservation(
        id_combination=int(row["id_combination"]),
        id_campus=int(row["id_campus"]),
        status=str(row["status"]),
        price_per_hour=Decimal(str(row["price_per_hour"])),
        member_field_ids=field_ids,
    )


def find_field_combination_price_per_hour_by_fields(
    db: Session,
    field_ids: Iterable[int],
) -> Optional[Decimal]:
    normalized_ids = sorted({int(field_id) for field_id in field_ids if field_id is not None})
    if not normalized_ids:
        return None
    query = text(
        """
        WITH candidate AS (
            SELECT
                c.price_per_hour,
                c.status,
                c.updated_at,
                array_agg(m.id_field ORDER BY m.sort_order, m.id_field) AS member_ids
            FROM booking.field_combination c
            JOIN booking.field_combination_member m
              ON m.id_combination = c.id_combination
            GROUP BY c.id_combination, c.price_per_hour, c.status, c.updated_at
        )
        SELECT price_per_hour
        FROM candidate
        WHERE member_ids = CAST(:member_ids AS bigint[])
        ORDER BY
            CASE WHEN lower(status) = 'active' THEN 0 ELSE 1 END,
            updated_at DESC NULLS LAST
        LIMIT 1
        """
    ).bindparams(bindparam("member_ids", type_=ARRAY(BIGINT())))
    row = db.execute(query, {"member_ids": list(normalized_ids)}).mappings().first()
    if row is None or row["price_per_hour"] is None:
        return None
    return Decimal(str(row["price_per_hour"]))


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
        SET status = :status,
            updated_at = now()
        WHERE id_field = :field_id
        """
    )
    result = db.execute(query, {"status": status, "field_id": field_id})
    db.commit()
    return bool(result.rowcount)


__all__ = [
    "CampusSummary",
    "FieldCombinationForReservation",
    "find_field_combination_price_per_hour_by_fields",
    "get_field_combination_for_reservation",
    "get_campus_summary",
    "get_field_ids_by_campus",
    "get_field_summary",
    "get_field_summaries",
    "update_field_status",
]
