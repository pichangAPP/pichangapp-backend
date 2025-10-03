from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import Campus


def list_campuses_by_business(db: Session, business_id: int) -> List[Campus]:
    return (
        db.query(Campus)
        .filter(Campus.id_business == business_id)
        .order_by(Campus.id_campus)
        .all()
    )


def get_campus(db: Session, campus_id: int) -> Optional[Campus]:
    return db.query(Campus).filter(Campus.id_campus == campus_id).first()


def create_campus(db: Session, campus: Campus) -> Campus:
    db.add(campus)
    db.flush()
    return campus


def delete_campus(db: Session, campus: Campus) -> None:
    db.delete(campus)
