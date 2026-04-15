"""Publish error.log events to Kafka."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

ERROR_LOGS_TOPIC = os.getenv("ERROR_LOGS_TOPIC", "error.logs")

try:
    from confluent_kafka import Producer as KafkaProducerRuntime
except Exception as exc:  # pragma: no cover
    KafkaProducerRuntime = None  # type: ignore[assignment]
    _KAFKA_IMPORT_ERROR = exc
else:
    _KAFKA_IMPORT_ERROR = None


def kafka_enabled() -> bool:
    return bool(os.getenv("KAFKA_BOOTSTRAP_SERVERS"))


@lru_cache()
def _get_kafka_producer() -> Any:
    if KafkaProducerRuntime is None:
        raise RuntimeError(
            "Kafka client dependency missing. Install confluent_kafka to enable publishing."
        ) from _KAFKA_IMPORT_ERROR
    client_id = os.getenv("KAFKA_AUTH_CLIENT_ID", "auth-svc")
    return KafkaProducerRuntime(
        {
            "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
            "client.id": f"{client_id}-errors",
        }
    )


def build_error_log_event(*, event_type: str, payload: dict, source: str) -> dict:
    return {
        "event_id": str(uuid4()),
        "event_type": event_type,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "payload": payload,
    }


def publish_error_log_event(event: dict, *, key: str | None = None) -> None:
    if not kafka_enabled():
        logger.debug("Kafka disabled; skip error.log publish")
        return
    try:
        producer = _get_kafka_producer()
        body = json.dumps(event, ensure_ascii=True, default=str).encode("utf-8")
        producer.produce(ERROR_LOGS_TOPIC, key=key, value=body)
        producer.poll(0)
    except Exception:
        logger.exception("Failed to publish error.log event to Kafka")
