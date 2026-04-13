from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from app.core.error_codes import BOOKING_SERVICE_UNAVAILABLE, http_error
from app.integrations import auth_reader
from app.models import Business


def attach_business_manager_data(db: Session, businesses: Iterable[Business]) -> None:
    """Adjunta data de manager a negocios y a sus campus relacionados.

    Usado en: BusinessService.list_businesses, BusinessService.get_business y
    BusinessService.get_business_by_manager.
    """
    business_list = [business for business in businesses if business is not None]
    if not business_list:
        return

    manager_ids: set[int] = set()
    for business in business_list:
        if business.id_manager is not None:
            manager_ids.add(business.id_manager)
        for campus in getattr(business, "campuses", []) or []:
            if campus.id_manager is not None:
                manager_ids.add(campus.id_manager)

    try:
        managers = auth_reader.get_manager_summaries(db, manager_ids)
    except auth_reader.AuthReaderError as exc:
        raise http_error(
            BOOKING_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    for business in business_list:
        manager_id = business.id_manager
        business.manager = managers.get(manager_id) if manager_id else None  # type: ignore[attr-defined]
        for campus in getattr(business, "campuses", []) or []:
            campus_manager_id = campus.id_manager
            campus.manager = (  # type: ignore[attr-defined]
                managers.get(campus_manager_id) if campus_manager_id else None
            )
