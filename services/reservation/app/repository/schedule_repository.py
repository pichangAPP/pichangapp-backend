from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.models.schedule import Schedule


def get_schedule(db: Session, schedule_id: int) -> Optional[Schedule]:
    return (
        db.query(Schedule)
        .options(
            joinedload(Schedule.field),
            joinedload(Schedule.user),
        )
        .filter(Schedule.id_schedule == schedule_id)
        .first()
    )
