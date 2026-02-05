"""API routers for the payment service."""

from fastapi import APIRouter

from app.api.v1.payment_methods_routes import router as payment_methods_router
from app.api.v1.payment_routes import router as payment_router

router = APIRouter()
router.include_router(payment_router)
router.include_router(payment_methods_router)

__all__ = ["router", "payment_router", "payment_methods_router"]
