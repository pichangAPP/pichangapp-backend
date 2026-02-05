from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models import BusinessLegal


def get_business_legal(db: Session, legal_id: int) -> Optional[BusinessLegal]:
    return db.query(BusinessLegal).filter(BusinessLegal.id_business_legal == legal_id).first()


def get_business_legal_by_business(db: Session, business_id: int) -> Optional[BusinessLegal]:
    return db.query(BusinessLegal).filter(BusinessLegal.id_business == business_id).first()


def create_business_legal(db: Session, legal: BusinessLegal) -> BusinessLegal:
    db.add(legal)
    db.flush()
    return legal


def delete_business_legal(db: Session, legal: BusinessLegal) -> None:
    db.delete(legal)
