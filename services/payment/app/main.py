"""Entry point for the payment service."""

from fastapi import FastAPI

from app.api import router as api_router
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

app.include_router(api_router, prefix="/api/pichangapp")
