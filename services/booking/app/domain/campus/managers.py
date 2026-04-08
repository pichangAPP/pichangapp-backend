from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from app.core.error_codes import BOOKING_SERVICE_UNAVAILABLE, http_error
from app.integrations import auth_reader
from app.models import Campus


def attach_campus_manager_data(db: Session, campuses: Iterable[Campus]) -> None:
    """Adjunta la data del manager a los campus consultados.

    Usado en: CampusService.list_campuses y CampusService.get_campus.
    """
    campus_list = [campus for campus in campuses if campus is not None]
    if not campus_list:
        return

    manager_ids = {
        campus.id_manager for campus in campus_list if campus.id_manager is not None
    }
    try:
        managers = auth_reader.get_manager_summaries(db, manager_ids)
    except auth_reader.AuthReaderError as exc:
        raise http_error(
            BOOKING_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    for campus in campus_list:
        manager_id = campus.id_manager
        campus.manager = managers.get(manager_id) if manager_id else None  # type: ignore[attr-defined]
