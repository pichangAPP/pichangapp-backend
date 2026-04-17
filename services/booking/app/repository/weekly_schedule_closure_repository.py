from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import WeeklyScheduleClosure


def list_by_campus(db: Session, campus_id: int) -> List[WeeklyScheduleClosure]:
    return (
        db.query(WeeklyScheduleClosure)
        .filter(WeeklyScheduleClosure.id_campus == campus_id)
        .order_by(WeeklyScheduleClosure.weekday, WeeklyScheduleClosure.id_field, WeeklyScheduleClosure.id)
        .all()
    )


def get_by_id(db: Session, closure_id: int) -> Optional[WeeklyScheduleClosure]:
    return (
        db.query(WeeklyScheduleClosure)
        .filter(WeeklyScheduleClosure.id == closure_id)
        .first()
    )


def create(db: Session, row: WeeklyScheduleClosure) -> WeeklyScheduleClosure:
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def save(db: Session, row: WeeklyScheduleClosure) -> WeeklyScheduleClosure:
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete(db: Session, row: WeeklyScheduleClosure) -> None:
    db.delete(row)
    db.commit()
