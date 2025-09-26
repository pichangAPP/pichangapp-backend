from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models import Characteristic


def create_characteristic(db: Session, characteristic: Characteristic) -> Characteristic:
    db.add(characteristic)
    db.flush()
    return characteristic


def get_characteristic(db: Session, characteristic_id: int) -> Optional[Characteristic]:
    return (
        db.query(Characteristic)
        .filter(Characteristic.id_characteristic == characteristic_id)
        .first()
    )
