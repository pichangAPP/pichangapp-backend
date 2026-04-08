from fastapi import APIRouter

from app.core.error_codes import BOOKING_SERVICE_UNAVAILABLE, http_error
from app.core.kafka import BOOKING_EVENTS_TOPIC, build_booking_test_event, publish_event

router = APIRouter(prefix="/kafka", tags=["kafka"])


@router.post("/test")
def publish_booking_test_event() -> dict:
    event = build_booking_test_event()
    try:
        publish_event(event, topic=BOOKING_EVENTS_TOPIC, key=event["booking_id"])
    except Exception as exc:  # pragma: no cover - surface Kafka connectivity issues
        raise http_error(
            BOOKING_SERVICE_UNAVAILABLE,
            detail="Kafka publish failed",
        ) from exc
    return {"status": "sent", "topic": BOOKING_EVENTS_TOPIC, "event": event}


__all__ = ["router"]
