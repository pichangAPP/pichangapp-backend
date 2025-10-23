"""Centralized exception handlers for the Notification service."""
from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def _flatten_detail(detail: Any) -> str:
    """Convert arbitrary exception detail payloads into a string message."""
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        if "detail" in detail:
            nested = detail["detail"]
            if isinstance(nested, str):
                return nested
        return "; ".join(f"{key}: {value}" for key, value in detail.items())
    if isinstance(detail, Iterable) and not isinstance(detail, (bytes, bytearray)):
        return "; ".join(_flatten_detail(item) for item in detail)
    if detail is None:
        return "An error occurred"
    return str(detail)


def register_exception_handlers(app: FastAPI) -> None:
    """Register FastAPI exception handlers that return a normalized JSON payload."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):  # type: ignore[override]
        detail = _flatten_detail(exc.detail)
        response = JSONResponse(status_code=exc.status_code, content={"detail": detail})

        if exc.headers:
            for key, value in exc.headers.items():
                response.headers[key] = value

        return response

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:  # type: ignore[override]
        messages = []
        for error in exc.errors():
            location = [str(loc) for loc in error.get("loc", []) if loc != "body"]
            message = error.get("msg", "Invalid input")
            if location:
                messages.append(f"{'.'.join(location)}: {message}")
            else:
                messages.append(message)

        detail = "; ".join(messages) if messages else "Invalid request"
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:  # type: ignore[override]
        logger.exception(
            "Unhandled exception while processing %s %s", request.method, request.url
        )
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})


__all__ = ["register_exception_handlers"]
