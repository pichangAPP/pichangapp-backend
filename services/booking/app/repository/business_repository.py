from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import Business, Campus, Field, Sport


def list_businesses(db: Session) -> List[Business]:
    return (
        db.query(Business)
        .options(
            joinedload(Business.manager),
            selectinload(Business.images),
            selectinload(Business.campuses)
            .selectinload(Campus.images),
            selectinload(Business.campuses)
            .selectinload(Campus.fields)
            .selectinload(Field.images),
            selectinload(Business.campuses)
            .selectinload(Campus.fields)
            .selectinload(Field.sport)
            .selectinload(Sport.modality),
        )
        .all()
    )


def get_business(db: Session, business_id: int) -> Optional[Business]:
    return (
        db.query(Business)
        .options(
            joinedload(Business.manager),
            selectinload(Business.images),
            selectinload(Business.campuses)
            .selectinload(Campus.images),
            selectinload(Business.campuses)
            .selectinload(Campus.fields)
            .selectinload(Field.images),
            selectinload(Business.campuses)
            .selectinload(Campus.fields)
            .selectinload(Field.sport)
            .selectinload(Sport.modality),
        )
        .filter(Business.id_business == business_id)
        .first()
    )


def create_business(db: Session, business: Business) -> Business:
    db.add(business)
    db.flush()
    return business


def delete_business(db: Session, business: Business) -> None:
    db.delete(business)