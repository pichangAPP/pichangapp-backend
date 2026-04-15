"""Centralized exception handlers for the Auth service."""
from __future__ import annotations

import logging
import os
import socket
import traceback
from collections.abc import Iterable
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.kafka_errors import build_error_log_event, publish_error_log_event

logger = logging.getLogger(__name__)
SERVICE_NAME = os.getenv("SERVICE_NAME", "auth-service")


def _flatten_detail(detail: Any) -> str:
    """Convert arbitrary exception detail payloads into a string message."""
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        if "detail" in detail:
            nested = detail["detail"]
            if isinstance(nested, str):
                return nested
        if "message" in detail and isinstance(detail["message"], str):
            return detail["message"]
        return "; ".join(f"{key}: {value}" for key, value in detail.items())
    if isinstance(detail, Iterable) and not isinstance(detail, (bytes, bytearray)):
        return "; ".join(_flatten_detail(item) for item in detail)
    if detail is None:
        return "An error occurred"
    return str(detail)


def _build_error_payload(
    detail: Any,
    *,
    default_code: str,
    default_message: str,
) -> dict[str, Any]:
    if isinstance(detail, dict):
        payload: dict[str, Any] = {}
        code = detail.get("code") or default_code
        message = detail.get("message") or detail.get("detail") or default_message
        payload["code"] = code
        payload["message"] = message
        if "detail" in detail and detail["detail"] not in (None, message):
            payload["detail"] = detail["detail"]
        if "errors" in detail:
            payload["errors"] = detail["errors"]
        return payload

    return {
        "code": default_code,
        "message": default_message,
        "detail": _flatten_detail(detail),
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Register FastAPI exception handlers that return a normalized JSON payload."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):  # type: ignore[override]
        payload = _build_error_payload(
            exc.detail,
            default_code="AUTH_ERROR",
            default_message="No se pudo procesar la solicitud.",
        )
        response = JSONResponse(status_code=exc.status_code, content=payload)

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
        response_body = {
            "code": "VALIDATION_ERROR",
            "message": "Datos inválidos.",
            "detail": detail,
        }
        return JSONResponse(status_code=422, content=response_body)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:  # type: ignore[override]
        logger.exception(
            "Unhandled exception while processing %s %s", request.method, request.url
        )
        try:
            trace_id = request.headers.get("x-trace-id") or request.headers.get(
                "x-request-id"
            )
            correlation_id = request.headers.get("x-correlation-id")
            payload = {
                "trace_id": trace_id,
                "correlation_id": correlation_id,
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "headers": dict(request.headers),
                "request_body": None,
                "response_status": 500,
                "response_body": {
                    "code": "INTERNAL_ERROR",
                    "message": "Ocurrió un error interno.",
                },
                "error_type": exc.__class__.__name__,
                "error_message": str(exc),
                "error_detail": None,
                "stack_trace": "".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__)
                ),
                "entity": "auth",
                "entity_id": None,
                "user_id": request.headers.get("x-user-id"),
                "tenant_id": request.headers.get("x-tenant-id"),
                "service_name": SERVICE_NAME,
                "host": socket.gethostname(),
                "ip_client": request.client.host if request.client else None,
                "duration_ms": None,
            }
            event = build_error_log_event(
                event_type="error.log",
                payload=payload,
                source=SERVICE_NAME,
            )
            publish_error_log_event(event, key=trace_id or correlation_id)
        except Exception:
            logger.exception("Failed to publish unhandled error to Kafka")
        return JSONResponse(
            status_code=500,
            content={"code": "INTERNAL_ERROR", "message": "Ocurrió un error interno."},
        )


__all__ = ["register_exception_handlers"]
