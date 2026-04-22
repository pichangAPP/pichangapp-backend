"""Routes for handling notification related requests."""

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool

from app.core.database import SessionLocal
from app.core.reservation_pass_ratelimit import (
    business_request_rate_limit_exceeded,
    client_ip_from_request,
    reservation_pass_rate_limit_exceeded,
)
from app.domain.notification.notify_push import notify_user_from_event
from app.domain.notification.attachments import (
    build_pass_link,
    build_reservation_pass,
    parse_pass_token,
)
from app.schemas import BusinessRequestNotification, NotificationRequest
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


@router.post("/send-push", status_code=status.HTTP_202_ACCEPTED)
async def send_push_notification(
    payload: NotificationRequest,
) -> dict[str, str]:
    """Send push notification to reservation user and campus manager (when available)."""
    if payload.id_user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="id_user is required to send push notifications",
        )

    def _dispatch_push() -> None:
        # Sesión dedicada al worker: SQLAlchemy Session no es thread-safe con la del request.
        db = SessionLocal()
        try:
            notify_user_from_event(
                db,
                id_user=payload.id_user,
                id_campus=payload.rent.campus.id_campus,
                event_type="rent.verdict",
                rent_id=payload.rent.rent_id,
                schedule_day=payload.rent.schedule_day,
                status=payload.rent.status,
            )
        finally:
            db.close()

    await run_in_threadpool(_dispatch_push)
    return {"detail": "Push notification dispatched"}


@router.post("/business-request", status_code=status.HTTP_202_ACCEPTED)
async def send_business_request_notification(
    request: Request,
    payload: BusinessRequestNotification,
) -> dict[str, str]:
    """Send applicant confirmation email and internal review email for business requests."""

    ip = client_ip_from_request(
        request.headers.get("x-forwarded-for"),
        request.client.host if request.client else None,
    )
    if business_request_rate_limit_exceeded(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes. Intenta de nuevo en un minuto.",
        )

    await run_in_threadpool(_email_service.send_business_request_notification, payload)
    return {
        "message": "Solicitud recibida correctamente",
        "status": "queued",
    }


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
