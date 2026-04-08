from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.error_codes import BOOKING_BAD_REQUEST, BUSINESS_NOT_FOUND, http_error
from app.models import Business
from app.repository import business_repository


def get_business_or_error(db: Session, business_id: int) -> Business:
    """Obtiene un negocio por id o lanza un error controlado.

    Usado en: CampusService (list/get/create), BusinessLegalService y
    BusinessSocialMediaService.
    """
    business = business_repository.get_business(db, business_id)
    if not business:
        raise http_error(
            BUSINESS_NOT_FOUND,
            detail=f"Business {business_id} not found",
        )
    return business


def validate_business_entity(business: Business) -> None:
    """Valida las reglas del negocio antes de persistir cambios.

    Usado en: BusinessService.create_business y BusinessService.update_business.
    """
    if business.min_price is not None and float(business.min_price) < 0:
        raise http_error(
            BOOKING_BAD_REQUEST,
            detail="min_price must be zero or greater",
        )
