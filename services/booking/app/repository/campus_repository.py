from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import Campus,Field,Sport


def list_campuses_by_business(db: Session, business_id: int) -> List[Campus]:
    return (
        db.query(Campus)
        .options(
            joinedload(Campus.manager),
            selectinload(Campus.characteristic),
            selectinload(Campus.images),
            selectinload(Campus.fields)
            .selectinload(Field.sport)
            .selectinload(Sport.modality),
            selectinload(Campus.fields).selectinload(Field.images),
        )
        .filter(Campus.id_business == business_id)
        .order_by(Campus.id_campus)
        .all()
    )


def get_campus(db: Session, campus_id: int) -> Optional[Campus]:
    return (
        db.query(Campus)
        .options(
            joinedload(Campus.manager),
            selectinload(Campus.characteristic),
            selectinload(Campus.images),
            selectinload(Campus.fields)
            .selectinload(Field.sport)
            .selectinload(Sport.modality),
            selectinload(Campus.fields).selectinload(Field.images),
        )
        .filter(Campus.id_campus == campus_id)
        .first()
    )


def create_campus(db: Session, campus: Campus) -> Campus:
    db.add(campus)
    db.flush()
    return campus


def delete_campus(db: Session, campus: Campus) -> None:
    db.delete(campus)