from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from functools import lru_cache
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from confluent_kafka import Producer as KafkaProducer
else:
    KafkaProducer = Any  # type: ignore[misc]

try:
    from confluent_kafka import Producer as KafkaProducerRuntime
except Exception as exc:  # pragma: no cover - optional dependency in some environments
    KafkaProducerRuntime = None  # type: ignore[assignment]
    _KAFKA_IMPORT_ERROR = exc

logger = logging.getLogger(__name__)

BOOKING_EVENTS_TOPIC = os.getenv("BOOKING_EVENTS_TOPIC", "booking.events")
ERROR_LOGS_TOPIC = os.getenv("ERROR_LOGS_TOPIC", "error.logs")


def kafka_enabled() -> bool:
    return bool(os.getenv("KAFKA_BOOTSTRAP_SERVERS"))


@lru_cache()
def get_kafka_producer() -> KafkaProducer:
    if KafkaProducerRuntime is None:
        raise RuntimeError(
            "Kafka client dependency missing. Install confluent_kafka to enable publishing."
        ) from _KAFKA_IMPORT_ERROR
    # Use booking-specific client id to avoid collisions across services.
    client_id = os.getenv("KAFKA_BOOKING_CLIENT_ID", "booking-svc")
    config = {
        # Default to the Docker Compose broker hostname.
        "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
        "client.id": client_id,
    }
    return KafkaProducerRuntime(config)


def build_event(*, event_type: str, payload: dict, source: str = "booking") -> dict:
    return {
        "event_id": str(uuid4()),
        "event_type": event_type,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "payload": payload,
    }


def build_booking_test_event() -> dict:
    booking_id = str(uuid4())
    return {
        "event_id": str(uuid4()),
        "event_type": "booking.requested",
        "booking_id": booking_id,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "source": "booking",
        "payload": {"status": "requested"},
    }


def publish_event(
    event: dict, *, topic: str = BOOKING_EVENTS_TOPIC, key: str | None = None
) -> None:
    producer = get_kafka_producer()
    payload = json.dumps(event).encode("utf-8")
    producer.produce(topic, key=key, value=payload)
    producer.flush(5)


def publish_error_event(
    event: dict,
    *,
    topic: str = ERROR_LOGS_TOPIC,
    key: str | None = None,
) -> None:
    """Publish error events without blocking request handling."""
    if not kafka_enabled():
        logger.info("Kafka disabled; skipping error event %s", event.get("event_type"))
        return
    producer = get_kafka_producer()
    payload = json.dumps(event, ensure_ascii=True).encode("utf-8")
    producer.produce(topic, key=key, value=payload)
    producer.poll(0)


__all__ = [
    "BOOKING_EVENTS_TOPIC",
    "ERROR_LOGS_TOPIC",
    "kafka_enabled",
    "build_event",
    "build_booking_test_event",
    "publish_event",
    "publish_error_event",
]
