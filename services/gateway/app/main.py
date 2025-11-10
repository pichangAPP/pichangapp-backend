import os
from typing import Dict

import httpx
from fastapi import FastAPI, HTTPException, Request
from starlette.responses import Response
from dotenv import load_dotenv

from app.core.error_handlers import register_exception_handlers

load_dotenv()


app = FastAPI(title="Pichangapp API Gateway")

register_exception_handlers(app)


SERVICE_URLS: Dict[str, str] = {
    "auth": os.getenv("AUTH_SERVICE_URL", "http://localhost:8000"),
    "users": os.getenv("AUTH_SERVICE_URL", "http://localhost:8000"),  # Users are part of Auth service
    "booking": os.getenv("BOOKING_SERVICE_URL", "http://localhost:8001"),
    "reservation": os.getenv("RESERVATION_SERVICE_URL", "http://localhost:8002"),
    "payment": os.getenv("PAYMENT_SERVICE_URL", "http://localhost:8003"),
    "notification": os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8004"),
    "analytics": os.getenv("ANALYTICS_SERVICE_URL", "http://localhost:8005"),
    "chatbot": os.getenv("CHATBOT_SERVICE_URL", "http://localhost:8006"),
}

FORWARDED_HEADERS = {"content-encoding", "transfer-encoding", "connection"}
SUPPORTED_METHODS = [
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "OPTIONS",
]


async def _proxy_request(request: Request, service_key: str, path: str) -> Response:
    base_url = SERVICE_URLS[service_key].rstrip("/")
    target_url = f"{base_url}{path}"

    headers = dict(request.headers)
    headers.pop("host", None)

    try:
        body = await request.body()
    except Exception:  # defensive, body reading rarely fails
        body = b""

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=30.0)) as client:
            response = await client.request(
                request.method,
                target_url,
                content=body if body else None,
                headers=headers,
                params=request.query_params,
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Error forwarding request to {service_key} service: {exc}",
        ) from exc

    filtered_headers = {
        key: value
        for key, value in response.headers.items()
        if key.lower() not in FORWARDED_HEADERS
    }

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=filtered_headers,
        media_type=response.headers.get("content-type"),
    )


def _build_path(prefix: str, path: str) -> str:
    if path:
        return f"{prefix}/{path}"
    return prefix

#  Auth Service Proxies

@app.api_route(
    "/api/pichangapp/v1/auth",
    methods=SUPPORTED_METHODS,
    include_in_schema=False,
)
async def proxy_auth_root(request: Request):
    return await _proxy_request(request, "auth", "/api/pichangapp/v1/auth")


@app.api_route(
    "/api/pichangapp/v1/auth/{path:path}",
    methods=SUPPORTED_METHODS,
    include_in_schema=False,
)
async def proxy_auth(request: Request, path: str):
    target_path = _build_path("/api/pichangapp/v1/auth", path)
    return await _proxy_request(request, "auth", target_path)


@app.api_route(
    "/api/pichangapp/v1/users",
    methods=SUPPORTED_METHODS,
    include_in_schema=False,
)
async def proxy_users_root(request: Request):
    return await _proxy_request(request, "users", "/api/pichangapp/v1/users")

@app.api_route(
    "/api/pichangapp/v1/users/{path:path}",
    methods=SUPPORTED_METHODS,
    include_in_schema=False,
)
async def proxy_users(request: Request, path: str):
    target_path = _build_path("/api/pichangapp/v1/users", path)
    return await _proxy_request(request, "users", target_path)

#  Booking Service Proxies
@app.api_route(
    "/api/pichangapp/v1/booking",
    methods=SUPPORTED_METHODS,
    include_in_schema=False,
)
async def proxy_booking_root(request: Request):
    return await _proxy_request(request, "booking", "/api/pichangapp/v1/booking")


@app.api_route(
    "/api/pichangapp/v1/booking/{path:path}",
    methods=SUPPORTED_METHODS,
    include_in_schema=False,
)
async def proxy_booking(request: Request, path: str):
    target_path = _build_path("/api/pichangapp/v1/booking", path)
    return await _proxy_request(request, "booking", target_path)

# Reservation Service Proxies

@app.api_route(
    "/api/pichangapp/v1/reservation",
    methods=SUPPORTED_METHODS,
    include_in_schema=False,
)
async def proxy_reservation_root(request: Request):
    return await _proxy_request(request, "reservation", "/api/pichangapp/v1/reservation")


@app.api_route(
    "/api/pichangapp/v1/reservation/{path:path}",
    methods=SUPPORTED_METHODS,
    include_in_schema=False,
)
async def proxy_reservation(request: Request, path: str):
    target_path = _build_path("/api/pichangapp/v1/reservation", path)
    return await _proxy_request(request, "reservation", target_path)


# Notification Service Proxies

@app.api_route(
    "/api/pichangapp/v1/notification",
    methods=SUPPORTED_METHODS,
    include_in_schema=False,
)
async def proxy_notification_root(request: Request):
    return await _proxy_request(request, "notification", "/api/pichangapp/v1/notification")


@app.api_route(
    "/api/pichangapp/v1/notification/{path:path}",
    methods=SUPPORTED_METHODS,
    include_in_schema=False,
)
async def proxy_notification(request: Request, path: str):
    target_path = _build_path("/api/pichangapp/v1/notification", path)
    return await _proxy_request(request, "notification", target_path)


# Chatbot Service Proxies

@app.api_route(
    "/api/pichangapp/v1/chatbot",
    methods=SUPPORTED_METHODS,
    include_in_schema=False,
)
async def proxy_chatbot_root(request: Request):
    return await _proxy_request(request, "chatbot", "/api/pichangapp/v1/chatbot")


@app.api_route(
    "/api/pichangapp/v1/chatbot/{path:path}",
    methods=SUPPORTED_METHODS,
    include_in_schema=False,
)
async def proxy_chatbot(request: Request, path: str):
    target_path = _build_path("/api/pichangapp/v1/chatbot", path)
    return await _proxy_request(request, "chatbot", target_path)