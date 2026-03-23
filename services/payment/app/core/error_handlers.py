"""Centralized exception handlers for the Payment service."""

from __future__ import annotations

import json
import logging
import os
import socket
import time
import traceback
from collections.abc import Iterable
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.kafka import (
    ERROR_LOGS_TOPIC,
    build_event,
    kafka_enabled,
    publish_error_event,
)

logger = logging.getLogger(__name__)
SERVICE_NAME = os.getenv("SERVICE_NAME", "payment-service")
SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie"}


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

        await _emit_error_event(
            request=request,
            exc=exc,
            status_code=exc.status_code,
            response_body={"detail": detail},
            error_detail=detail,
            stack_trace=None,
        )
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
        response_body = {"detail": detail}
        await _emit_error_event(
            request=request,
            exc=exc,
            status_code=422,
            response_body=response_body,
            error_detail=detail,
            stack_trace=None,
        )
        return JSONResponse(status_code=422, content=response_body)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:  # type: ignore[override]
        logger.exception(
            "Unhandled exception while processing %s %s", request.method, request.url
        )
        await _emit_error_event(
            request=request,
            exc=exc,
            status_code=500,
            response_body={"detail": "Internal server error"},
            error_detail=str(exc),
            stack_trace=traceback.format_exc(),
        )
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})


def _mask_headers(headers: dict[str, str]) -> dict[str, str]:
    sanitized: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADERS:
            sanitized[key] = "***"
        else:
            sanitized[key] = value
    return sanitized


async def _read_request_body(request: Request) -> Any | None:
    try:
        raw_body = await request.body()
    except Exception:
        return None
    if not raw_body:
        return None
    try:
        return json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        try:
            return raw_body.decode("utf-8")
        except UnicodeDecodeError:
            return None


def _duration_ms(request: Request) -> int | None:
    start_time = getattr(request.state, "start_time", None)
    if start_time is None:
        return None
    return int((time.perf_counter() - start_time) * 1000)


def _extract_context(request: Request) -> dict[str, Any]:
    context = getattr(request.state, "error_context", None)
    if isinstance(context, dict):
        return context
    return {}


def _get_header_value(request: Request, *names: str) -> str | None:
    for name in names:
        value = request.headers.get(name)
        if value:
            return value
    return None


async def _emit_error_event(
    *,
    request: Request,
    exc: Exception,
    status_code: int,
    response_body: dict[str, Any] | None,
    error_detail: str | None,
    stack_trace: str | None,
) -> None:
    if not kafka_enabled():
        return
    try:
        context = _extract_context(request)
        request_body = await _read_request_body(request)
        trace_id = context.get("trace_id") or _get_header_value(
            request, "x-trace-id", "trace-id", "trace_id", "x-request-id"
        )
        correlation_id = context.get("correlation_id") or _get_header_value(
            request, "x-correlation-id", "correlation-id", "correlation_id"
        )
        payload = {
            "trace_id": trace_id,
            "correlation_id": correlation_id,
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": _mask_headers(dict(request.headers)),
            "request_body": request_body,
            "response_status": status_code,
            "response_body": response_body,
            "error_type": exc.__class__.__name__,
            "error_message": _flatten_detail(error_detail) if error_detail else str(exc),
            "error_detail": error_detail,
            "stack_trace": stack_trace,
            "entity": context.get("entity"),
            "entity_id": context.get("entity_id"),
            "user_id": context.get("user_id")
            or _get_header_value(request, "x-user-id", "user-id"),
            "tenant_id": context.get("tenant_id")
            or _get_header_value(request, "x-tenant-id", "tenant-id"),
            "service_name": SERVICE_NAME,
            "host": socket.gethostname(),
            "ip_client": request.client.host if request.client else None,
            "duration_ms": _duration_ms(request),
        }
        event = build_event(
            event_type="error.log",
            payload=payload,
            source=SERVICE_NAME,
        )
        publish_error_event(
            event,
            topic=ERROR_LOGS_TOPIC,
            key=trace_id or correlation_id,
        )
    except Exception:
        logger.exception("Failed to publish error log event")


__all__ = ["register_exception_handlers"]
