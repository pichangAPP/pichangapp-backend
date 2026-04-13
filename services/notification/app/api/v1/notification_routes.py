"""Routes for handling notification related requests."""

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool

from app.core.reservation_pass_ratelimit import (
    client_ip_from_request,
    reservation_pass_rate_limit_exceeded,
)
from app.domain.notification.attachments import (
    build_pass_link,
    build_reservation_pass,
    parse_pass_token,
)
from app.schemas import NotificationRequest
from app.services import EmailService

router = APIRouter(prefix="/notifications", tags=["notifications"])

_email_service = EmailService()


@router.post("/send-email", status_code=status.HTTP_202_ACCEPTED)
async def send_email(payload: NotificationRequest) -> dict[str, str]:
    """Send the rent confirmation emails to the corresponding recipients."""

    await run_in_threadpool(_email_service.send_rent_notification, payload)
    return {"detail": "Emails sent"}


@router.post("/rent-approved", status_code=status.HTTP_202_ACCEPTED)
async def send_rent_approved_notification(
    payload: NotificationRequest,
) -> dict[str, str]:
    """Send reservation approval email to the user."""

    await run_in_threadpool(_email_service.send_user_confirmation, payload)
    return {"detail": "Reservation approval email sent"}


@router.get("/reservation-pass")
async def get_reservation_pass(request: Request, token: str) -> Response:
    """Devuelve la boleta PNG. El token va en query (?token=) para soportar JWT con puntos."""
    ip = client_ip_from_request(
        request.headers.get("x-forwarded-for"),
        request.client.host if request.client else None,
    )
    if reservation_pass_rate_limit_exceeded(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes. Intenta de nuevo en un minuto.",
        )

    payload = parse_pass_token(token.strip())
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Boleta no encontrada o enlace inválido.",
        )
    pass_link = build_pass_link(payload, firebase_url=None)

    def _render() -> bytes:
        attachment = build_reservation_pass(payload, pass_link=pass_link)
        return attachment.data

    data = await run_in_threadpool(_render)
    return Response(
        content=data,
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


__all__ = ["router"]
