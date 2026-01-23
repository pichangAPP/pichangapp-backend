import json
import os
from datetime import datetime, timezone
from functools import lru_cache
from uuid import uuid4

from confluent_kafka import Producer

BOOKING_EVENTS_TOPIC = os.getenv("BOOKING_EVENTS_TOPIC", "booking.events")


@lru_cache()
def get_kafka_producer() -> Producer:
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
