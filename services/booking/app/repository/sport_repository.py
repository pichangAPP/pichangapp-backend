from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models import Sport


def get_sport(db: Session, sport_id: int) -> Optional[Sport]:
    return db.get(Sport, sport_id)