"""Entry point for the Payment service."""

from fastapi import FastAPI

from app.core.error_handlers import register_exception_handlers

app = FastAPI(title="Payment Service")

register_exception_handlers(app)
