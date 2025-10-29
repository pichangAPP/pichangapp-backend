"""Entry point for the Notification service."""

from fastapi import FastAPI

from app.core.error_handlers import register_exception_handlers

app = FastAPI(title="Notification Service")

register_exception_handlers(app)
