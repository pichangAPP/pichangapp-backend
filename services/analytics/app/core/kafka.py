import json
import logging
import os
import threading
from typing import Iterable

from confluent_kafka import Consumer, KafkaError

logger = logging.getLogger(__name__)

BOOKING_EVENTS_TOPIC = os.getenv("BOOKING_EVENTS_TOPIC", "booking.events")


def kafka_enabled() -> bool:
    return bool(os.getenv("KAFKA_BOOTSTRAP_SERVERS"))


class KafkaConsumerWorker:
    def __init__(self, topics: Iterable[str]) -> None:
        self._topics = list(topics)
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        if self._topics:
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        consumer = Consumer(
            {
                "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
                "group.id": os.getenv("KAFKA_CONSUMER_GROUP", "analytics-cg"),
                "client.id": os.getenv("KAFKA_CLIENT_ID", "analytics-svc"),
                "auto.offset.reset": os.getenv("KAFKA_AUTO_OFFSET_RESET", "earliest"),
            }
        )
        consumer.subscribe(self._topics)
        logger.info("Kafka consumer started for topics: %s", self._topics)

        try:
            while not self._stop_event.is_set():
                message = consumer.poll(1.0)
                if message is None:
                    continue
                if message.error():
                    if message.error().code() != KafkaError._PARTITION_EOF:
                        logger.error("Kafka error: %s", message.error())
                    continue

                payload = message.value()
                try:
                    decoded = json.loads(payload.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    logger.warning("Kafka message not JSON: %s", payload)
                    continue

                event_type = decoded.get("event_type", "unknown")
                logger.info(
                    "Kafka event received topic=%s type=%s payload=%s",
                    message.topic(),
                    event_type,
                    decoded,
                )
        finally:
            consumer.close()
            logger.info("Kafka consumer stopped")


__all__ = ["BOOKING_EVENTS_TOPIC", "KafkaConsumerWorker", "kafka_enabled"]
