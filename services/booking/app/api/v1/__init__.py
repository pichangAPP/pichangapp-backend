from fastapi import APIRouter

from .business_routes import router as business_router
from .campus_routes import router as campus_router
from .characteristic_routes import router as characteristic_router
from .field_routes import router as field_router
from .image_routes import router as image_router

router = APIRouter()
router.include_router(business_router)
router.include_router(campus_router)
router.include_router(characteristic_router)
router.include_router(field_router)
router.include_router(image_router)

__all__ = [
    "router",
    "business_router",
    "campus_router",
    "characteristic_router",
    "field_router",
    "image_router",
]
