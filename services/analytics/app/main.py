"""Entry point for the Analytics service."""

from fastapi import FastAPI

from app.api import analytics_router
from app.core.config import settings
from app.core.database import Base, engine
from app.core.error_handlers import register_exception_handlers

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.PROJECT_NAME)

register_exception_handlers(app)

app.include_router(
    analytics_router,
    prefix="/api/pichangapp/v1/analytics",
)


__all__ = ["app"]
