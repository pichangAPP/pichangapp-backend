from __future__ import annotations

from datetime import datetime, timezone

from app.models import Campus


def update_campus_field_count(db, campus: Campus, *, delta: int) -> None:
    """Actualiza el contador de canchas del campus y deja el cambio en el flush.

    Usado en: FieldService.create_field y FieldService.delete_field.
    """
    current_value = int(campus.count_fields or 0)
    new_value = current_value + delta
    if new_value < 0:
        new_value = 0
    campus.count_fields = new_value
    campus.updated_at = datetime.now(timezone.utc)
    db.flush([campus])
