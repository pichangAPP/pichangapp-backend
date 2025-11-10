"""Routes for handling notification related requests."""

from fastapi import APIRouter, status
from fastapi.concurrency import run_in_threadpool

from app.schemas import NotificationRequest
from app.services import EmailService

router = APIRouter(prefix="/notifications", tags=["notifications"])

_email_service = EmailService()


@router.post("/send-email", status_code=status.HTTP_202_ACCEPTED)
async def send_email(payload: NotificationRequest) -> dict[str, str]:
    """Send the rent confirmation emails to the corresponding recipients."""

    await run_in_threadpool(_email_service.send_rent_notification, payload)
    return {"detail": "Emails sent"}


__all__ = ["router"]
