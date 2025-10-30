"""FastAPI application entry point for the chatbot service."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.v1 import router as v1_router
from app.core.config import settings
from app.core.error_handlers import register_exception_handlers

app = FastAPI(title=settings.PROJECT_NAME)

register_exception_handlers(app)

app.include_router(v1_router, prefix="/api/pichangapp/v1")

__all__ = ["app"]
