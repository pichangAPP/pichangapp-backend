"""Versioned API routes for the analytics service."""

from fastapi import APIRouter, Depends

from app.core.security import get_current_user

from .analytics_routes import router as analytics_router

router = APIRouter(dependencies=[Depends(get_current_user)])
router.include_router(analytics_router)

__all__ = ["router", "analytics_router"]
