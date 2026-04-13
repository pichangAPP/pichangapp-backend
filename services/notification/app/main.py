"""Entry point for the Notification service."""

from fastapi import FastAPI

from app.api import notification_router
from app.core.config import settings
from app.core.error_handlers import register_exception_handlers
from app.core.kafka import (
    KafkaConsumerWorker,
    RESERVATION_NOTIFICATIONS_TOPIC,
    kafka_enabled,
)

app = FastAPI(title=settings.PROJECT_NAME)

register_exception_handlers(app)

app.include_router(
    notification_router,
    prefix="/api/pichangapp/v1/notification",
)

kafka_worker: KafkaConsumerWorker | None = None
if kafka_enabled():
    # Start the consumer so emails are dispatched from Kafka events.
    kafka_worker = KafkaConsumerWorker([RESERVATION_NOTIFICATIONS_TOPIC])


@app.on_event("startup")
def _start_kafka_worker() -> None:
    if kafka_worker is not None:
        kafka_worker.start()


@app.on_event("shutdown")
def _stop_kafka_worker() -> None:
    if kafka_worker is not None:
        kafka_worker.stop()

__all__ = ["app"]
