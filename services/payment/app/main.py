"""Entry point for the Payment service."""

from fastapi import FastAPI

from app.api import router as api_router
from app.core.config import settings
from app.core.error_handlers import register_exception_handlers


app = FastAPI(title=settings.PROJECT_NAME)

register_exception_handlers(app)

app.include_router(
    api_router,
    prefix="/api/pichangapp/v1/payment",
)


__all__ = ["app"]
