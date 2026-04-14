"""API routers for the notification service."""

from app.api.v1.notification_routes import router as notification_router
from app.api.v1.push_routes import router as push_router

__all__ = ["notification_router", "push_router"]
