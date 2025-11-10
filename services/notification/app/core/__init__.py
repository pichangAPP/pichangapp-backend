"""Core utilities for the notification service."""

from app.core.config import settings
from app.core.error_handlers import register_exception_handlers

__all__ = ["settings", "register_exception_handlers"]
