from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import Field


def list_fields_by_campus(db: Session, campus_id: int) -> List[Field]:
    return (
        db.query(Field).filter(Field.id_campus == campus_id).order_by(Field.id_field).all()
    )


def get_field(db: Session, field_id: int) -> Optional[Field]:
    return db.query(Field).filter(Field.id_field == field_id).first()


def create_field(db: Session, field: Field) -> Field:
    db.add(field)
    db.flush()
    return field


def delete_field(db: Session, field: Field) -> None:
    db.delete(field)
