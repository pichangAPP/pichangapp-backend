"""Version 1 API routes for the payment service."""

from fastapi import APIRouter

from .membership_routes import router as membership_router

router = APIRouter()
router.include_router(membership_router)

__all__ = ["router"]
