"""Entry point for the Payment service."""

import time

from fastapi import FastAPI

from app import models  # noqa: F401  # Ensure models are registered for metadata.
from app.api import router as api_router
from app.core.config import settings
from app.core.database import Base, engine, ensure_payment_schema, verify_database_connection
from app.core.error_handlers import register_exception_handlers

verify_database_connection()
ensure_payment_schema()
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.PROJECT_NAME)

register_exception_handlers(app)


@app.middleware("http")
async def _capture_request_start_time(request, call_next):
    request.state.start_time = time.perf_counter()
    return await call_next(request)

app.include_router(
    api_router,
    prefix="/api/pichangapp/v1/payment",
)

__all__ = ["app"]
