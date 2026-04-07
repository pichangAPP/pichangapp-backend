from fastapi import APIRouter, Depends

from .business_legal_routes import router as business_legal_router
from .business_routes import router as business_router
from .business_social_media_routes import router as business_social_media_router
from .campus_routes import router as campus_router
from .characteristic_routes import router as characteristic_router
from .field_combination_routes import router as field_combination_router
from .field_routes import router as field_router
from .image_routes import router as image_router
from .kafka_routes import router as kafka_router
from app.core.security import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])
router.include_router(business_legal_router)
router.include_router(business_router)
router.include_router(business_social_media_router)
router.include_router(campus_router)
router.include_router(characteristic_router)
router.include_router(field_router)
router.include_router(field_combination_router)
router.include_router(image_router)
router.include_router(kafka_router)

__all__ = [
    "router",
    "business_legal_router",
    "business_router",
    "business_social_media_router",
    "campus_router",
    "characteristic_router",
    "field_router",
    "field_combination_router",
    "image_router",
    "kafka_router",
]
