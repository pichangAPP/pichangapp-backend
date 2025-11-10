"""Entry point for the Notification service."""

from fastapi import FastAPI

from app.api import notification_router
from app.core.config import settings
from app.core.error_handlers import register_exception_handlers

app = FastAPI(title=settings.PROJECT_NAME)

register_exception_handlers(app)

app.include_router(
    notification_router,
    prefix="/api/pichangapp/v1/notification",
)

__all__ = ["app"]
