from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.status_catalog import StatusCatalog


def get_status(db: Session, status_id: int) -> Optional[StatusCatalog]:
    return (
        db.query(StatusCatalog)
        .filter(StatusCatalog.id_status == status_id)
        .first()
    )


def get_status_by_entity_code(
    db: Session,
    *,
    entity: str,
    code: str,
    exclude_status_id: Optional[int] = None,
) -> Optional[StatusCatalog]:
    query = (
        db.query(StatusCatalog)
        .filter(StatusCatalog.entity == entity)
        .filter(StatusCatalog.code == code)
    )
    if exclude_status_id is not None:
        query = query.filter(StatusCatalog.id_status != exclude_status_id)
    return query.first()


def list_statuses(
    db: Session,
    *,
    entity: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> list[StatusCatalog]:
    query = db.query(StatusCatalog)
    if entity is not None:
        query = query.filter(StatusCatalog.entity == entity)
    if is_active is not None:
        query = query.filter(StatusCatalog.is_active == is_active)
    return query.order_by(StatusCatalog.sort_order, StatusCatalog.id_status).all()


def create_status(db: Session, status_data: dict) -> StatusCatalog:
    status = StatusCatalog(**status_data)
    db.add(status)
    db.commit()
    db.refresh(status)
    return status


def save_status(db: Session, status: StatusCatalog) -> StatusCatalog:
    db.flush()
    db.commit()
    db.refresh(status)
    return status


def delete_status(db: Session, status: StatusCatalog) -> None:
    db.delete(status)
    db.commit()
