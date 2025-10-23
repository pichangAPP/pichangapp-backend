"""Entry point for the Analytics service."""

from fastapi import FastAPI

from app.core.error_handlers import register_exception_handlers

app = FastAPI(title="Analytics Service")

register_exception_handlers(app)
