"""Entry point for the Payment service."""

from fastapi import FastAPI

from app.api import payment_router
from app.core.config import settings
from app.core.database import Base, engine
from app.core.error_handlers import register_exception_handlers

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.PROJECT_NAME)

register_exception_handlers(app)

app.include_router(
    payment_router,
    prefix="/api/pichangapp/v1/payment",
)


__all__ = ["app"]
