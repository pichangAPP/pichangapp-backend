from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.models.field_combination import FieldCombination, FieldCombinationMember


def get_combination(db: Session, combination_id: int) -> Optional[FieldCombination]:
    return (
        db.query(FieldCombination)
        .options(joinedload(FieldCombination.members).joinedload(FieldCombinationMember.field))
        .filter(FieldCombination.id_combination == combination_id)
        .first()
    )


def list_combinations_by_campus(
    db: Session,
    campus_id: int,
    *,
    active_only: bool = False,
) -> list[FieldCombination]:
    q = (
        db.query(FieldCombination)
        .options(joinedload(FieldCombination.members).joinedload(FieldCombinationMember.field))
        .filter(FieldCombination.id_campus == campus_id)
        .order_by(FieldCombination.name)
    )
    if active_only:
        q = q.filter(FieldCombination.status == "active")
    return q.all()


def list_combinations_containing_field(
    db: Session,
    field_id: int,
    *,
    active_only: bool = True,
) -> list[FieldCombination]:
    q = (
        db.query(FieldCombination)
        .join(FieldCombinationMember)
        .options(joinedload(FieldCombination.members).joinedload(FieldCombinationMember.field))
        .filter(FieldCombinationMember.id_field == field_id)
        .distinct()
        .order_by(FieldCombination.name)
    )
    if active_only:
        q = q.filter(FieldCombination.status == "active")
    return q.all()


def create_combination(db: Session, combo: FieldCombination) -> FieldCombination:
    db.add(combo)
    db.commit()
    db.refresh(combo)
    return combo


def save_combination(db: Session, combo: FieldCombination) -> FieldCombination:
    db.commit()
    db.refresh(combo)
    return combo


def delete_combination(db: Session, combo: FieldCombination) -> None:
    db.delete(combo)
    db.commit()
