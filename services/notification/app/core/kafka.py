"""Kafka consumer utilities for reservation notification events."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Iterable

from confluent_kafka import Consumer, KafkaError

from app.core.database import SessionLocal
from app.domain.notification.notify_push import notify_user_from_event
from app.schemas import NotificationRequest
from app.services import EmailService

logger = logging.getLogger(__name__)

RESERVATION_NOTIFICATIONS_TOPIC = os.getenv(
    "RESERVATION_NOTIFICATIONS_TOPIC",
    "reservation.notifications",
)

# These knobs allow tuning retries without code changes.
KAFKA_EMAIL_RETRY_ATTEMPTS = int(os.getenv("KAFKA_EMAIL_RETRY_ATTEMPTS", "3"))
KAFKA_EMAIL_RETRY_BASE_SECONDS = float(os.getenv("KAFKA_EMAIL_RETRY_BASE_SECONDS", "2"))
KAFKA_EMAIL_RETRY_MAX_SECONDS = float(os.getenv("KAFKA_EMAIL_RETRY_MAX_SECONDS", "30"))


def kafka_enabled() -> bool:
    return bool(os.getenv("KAFKA_BOOTSTRAP_SERVERS"))


class KafkaConsumerWorker:
    """Background worker that consumes reservation events and sends emails."""

    def __init__(self, topics: Iterable[str]) -> None:
        self._topics = list(topics)
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._email_service = EmailService()

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
                # Default to the Docker Compose broker hostname.
                "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
                # Notification-specific consumer group and client id.
                "group.id": os.getenv(
                    "KAFKA_NOTIFICATION_CONSUMER_GROUP",
                    "notification-cg",
                ),
                "client.id": os.getenv(
                    "KAFKA_NOTIFICATION_CLIENT_ID",
                    "notification-svc",
                ),
                "auto.offset.reset": os.getenv(
                    "KAFKA_NOTIFICATION_AUTO_OFFSET_RESET",
                    "earliest",
                ),
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
                notification_payload = (
                    decoded.get("payload", {}) or {}
                ).get("notification")
                if not notification_payload:
                    logger.warning(
                        "Kafka event missing notification payload. type=%s payload=%s",
                        event_type,
                        decoded,
                    )
                    continue

                try:
                    notification = NotificationRequest(**notification_payload)
                except Exception as exc:
                    logger.warning(
                        "Invalid notification payload for event %s: %s",
                        event_type,
                        exc,
                    )
                    continue

                if event_type in ("rent.payment_received", "rent.booking_notice"):
                    self._retry_email_dispatch(
                        event_type=event_type,
                        email_action=lambda: self._email_service.send_rent_notification(
                            notification
                        ),
                    )
                    self._dispatch_push(event_type, notification)
                elif event_type in {"rent.verdict", "rent.approved", "rent.rejected"}:
                    self._retry_email_dispatch(
                        event_type=event_type,
                        email_action=lambda: self._email_service.send_user_confirmation(
                            notification
                        ),
                    )
                    self._dispatch_push(event_type, notification)
                else:
                    logger.info("Ignoring Kafka event type: %s", event_type)
        finally:
            consumer.close()
            logger.info("Kafka consumer stopped")

    @staticmethod
    def _dispatch_push(event_type: str, notification: NotificationRequest) -> None:
        """FCM independiente del correo: se intenta aunque el SMTP haya fallado."""
        db = SessionLocal()
        try:
            notify_user_from_event(
                db,
                id_user=notification.id_user,
                id_campus=notification.rent.campus.id_campus,
                event_type=event_type,
                rent_id=notification.rent.rent_id,
                schedule_day=notification.rent.schedule_day,
                status=notification.rent.status,
            )
        except Exception as exc:  # pragma: no cover - external dependencies
            logger.warning(
                "FCM dispatch failed for event %s user_id=%s: %s",
                event_type,
                notification.id_user,
                exc,
            )
        finally:
            db.close()

    @staticmethod
    def _retry_email_dispatch(*, event_type: str, email_action) -> None:
        """Reintentos solo para el correo."""
        attempts = max(1, KAFKA_EMAIL_RETRY_ATTEMPTS)
        for attempt in range(1, attempts + 1):
            try:
                email_action()
                return
            except Exception as exc:  # pragma: no cover - external dependencies
                if attempt >= attempts:
                    logger.error(
                        "Email dispatch failed for event %s after %s attempts: %s",
                        event_type,
                        attempts,
                        exc,
                    )
                    return
                delay = min(
                    KAFKA_EMAIL_RETRY_BASE_SECONDS * (2 ** (attempt - 1)),
                    KAFKA_EMAIL_RETRY_MAX_SECONDS,
                )
                logger.warning(
                    "Email dispatch failed for event %s (attempt %s/%s). Retrying in %.1fs",
                    event_type,
                    attempt,
                    attempts,
                    delay,
                )
                time.sleep(delay)


__all__ = [
    "RESERVATION_NOTIFICATIONS_TOPIC",
    "KafkaConsumerWorker",
    "kafka_enabled",
]
