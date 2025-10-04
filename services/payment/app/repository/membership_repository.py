"""Data access helpers for memberships."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import Membership


def list_memberships(db: Session) -> List[Membership]:
    return db.query(Membership).all()


def get_membership(db: Session, membership_id: int) -> Optional[Membership]:
    return db.query(Membership).filter(Membership.id_membership == membership_id).first()


def create_membership(db: Session, membership: Membership) -> Membership:
    db.add(membership)
    db.flush()
    return membership


def delete_membership(db: Session, membership: Membership) -> None:
    db.delete(membership)
