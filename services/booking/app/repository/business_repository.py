from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import Business


def list_businesses(db: Session) -> List[Business]:
    return db.query(Business).all()


def get_business(db: Session, business_id: int) -> Optional[Business]:
    return db.query(Business).filter(Business.id_business == business_id).first()


def create_business(db: Session, business: Business) -> Business:
    db.add(business)
    db.flush()
    return business


def delete_business(db: Session, business: Business) -> None:
    db.delete(business)
