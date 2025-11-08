"""Entry point for the Analytics service."""

from fastapi import FastAPI

from app.api import v1_router
from app.core.config import settings
from app.core.database import Base, engine, verify_database_connection
from app.core.error_handlers import register_exception_handlers

verify_database_connection()
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.PROJECT_NAME)

register_exception_handlers(app)

app.include_router(
    v1_router,
    prefix="/api/pichangapp/v1",
)


__all__ = ["app"]
