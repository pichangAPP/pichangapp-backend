import json
import os
from datetime import datetime, timezone
from functools import lru_cache
from uuid import uuid4

try:
    from confluent_kafka import Producer
except Exception as exc:  # pragma: no cover - optional dependency in some environments
    Producer = None  # type: ignore[assignment]
    _KAFKA_IMPORT_ERROR = exc

BOOKING_EVENTS_TOPIC = os.getenv("BOOKING_EVENTS_TOPIC", "booking.events")


@lru_cache()
def get_kafka_producer() -> Producer:
    if Producer is None:  # type: ignore[comparison-overlap]
        raise RuntimeError(
            "Kafka client dependency missing. Install confluent_kafka to enable publishing."
        ) from _KAFKA_IMPORT_ERROR
    config = {
        "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        "client.id": os.getenv("KAFKA_CLIENT_ID", "booking-svc"),
    }
    return Producer(config)


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


def publish_event(event: dict, *, topic: str = BOOKING_EVENTS_TOPIC, key: str | None = None) -> None:
    producer = get_kafka_producer()
    payload = json.dumps(event).encode("utf-8")
    producer.produce(topic, key=key, value=payload)
    producer.flush(5)


__all__ = ["BOOKING_EVENTS_TOPIC", "build_booking_test_event", "publish_event"]
