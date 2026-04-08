"""Entry point for the Analytics service."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import v1_router
from app.core.config import settings
from app.core.database import Base, engine, verify_database_connection
from app.core.error_handlers import register_exception_handlers
from app.core.kafka import BOOKING_EVENTS_TOPIC, KafkaConsumerWorker, kafka_enabled

verify_database_connection()
Base.metadata.create_all(bind=engine)

kafka_worker: KafkaConsumerWorker | None = None
if kafka_enabled():
    kafka_worker = KafkaConsumerWorker([BOOKING_EVENTS_TOPIC])


@asynccontextmanager
async def lifespan(app: FastAPI):
    if kafka_worker is not None:
        kafka_worker.start()
    try:
        yield
    finally:
        if kafka_worker is not None:
            kafka_worker.stop()


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

register_exception_handlers(app)

app.include_router(
    v1_router,
    prefix="/api/pichangapp/v1",
)


__all__ = ["app"]
