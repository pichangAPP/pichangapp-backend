"""Kafka consumer for cross-service error logs."""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Iterable
from uuid import UUID

from confluent_kafka import Consumer, KafkaError
from sqlalchemy import text

from app.core.database import engine

logger = logging.getLogger(__name__)

ERROR_LOGS_TOPIC = os.getenv("ERROR_LOGS_TOPIC", "error.logs")


def kafka_enabled() -> bool:
    return bool(os.getenv("KAFKA_BOOTSTRAP_SERVERS"))


def _parse_uuid(value: str | None):
    if not value:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


def _to_json(value):
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=True)


def _normalize_payload(payload: dict) -> dict:
    return {
        "trace_id": _parse_uuid(payload.get("trace_id")),
        "correlation_id": _parse_uuid(payload.get("correlation_id")),
        "method": payload.get("method") or "UNKNOWN",
        "url": payload.get("url") or "",
        "path": payload.get("path"),
        "query_params": _to_json(payload.get("query_params")),
        "headers": _to_json(payload.get("headers")),
        "request_body": _to_json(payload.get("request_body")),
        "response_status": int(payload.get("response_status") or 500),
        "response_body": _to_json(payload.get("response_body")),
        "error_type": payload.get("error_type"),
        "error_message": payload.get("error_message"),
        "error_detail": payload.get("error_detail"),
        "stack_trace": payload.get("stack_trace"),
        "entity": payload.get("entity"),
        "entity_id": payload.get("entity_id"),
        "user_id": payload.get("user_id"),
        "tenant_id": payload.get("tenant_id"),
        "service_name": payload.get("service_name") or "unknown",
        "host": payload.get("host"),
        "ip_client": payload.get("ip_client"),
        "duration_ms": payload.get("duration_ms"),
    }


def _insert_error_log(payload: dict) -> None:
    data = _normalize_payload(payload)
    stmt = text(
        """
        INSERT INTO auth.error_log (
            trace_id,
            correlation_id,
            method,
            url,
            path,
            query_params,
            headers,
            request_body,
            response_status,
            response_body,
            error_type,
            error_message,
            error_detail,
            stack_trace,
            entity,
            entity_id,
            user_id,
            tenant_id,
            service_name,
            host,
            ip_client,
            duration_ms
        ) VALUES (
            :trace_id,
            :correlation_id,
            :method,
            :url,
            :path,
            CAST(:query_params AS JSONB),
            CAST(:headers AS JSONB),
            CAST(:request_body AS JSONB),
            :response_status,
            CAST(:response_body AS JSONB),
            :error_type,
            :error_message,
            :error_detail,
            :stack_trace,
            :entity,
            :entity_id,
            :user_id,
            :tenant_id,
            :service_name,
            :host,
            :ip_client,
            :duration_ms
        )
        """
    )
    with engine.begin() as connection:
        connection.execute(stmt, data)


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
                "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
                "group.id": os.getenv("KAFKA_AUTH_CONSUMER_GROUP", "auth-error-cg"),
                "client.id": os.getenv("KAFKA_AUTH_CLIENT_ID", "auth-svc"),
                "auto.offset.reset": os.getenv(
                    "KAFKA_AUTH_AUTO_OFFSET_RESET", "earliest"
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

                if decoded.get("event_type") != "error.log":
                    continue

                event_payload = decoded.get("payload")
                if not isinstance(event_payload, dict):
                    logger.warning("Kafka error event missing payload: %s", decoded)
                    continue

                try:
                    _insert_error_log(event_payload)
                except Exception as exc:  # pragma: no cover - DB side effects
                    logger.error("Failed to insert error log: %s", exc)
        finally:
            consumer.close()
            logger.info("Kafka consumer stopped")


__all__ = ["ERROR_LOGS_TOPIC", "KafkaConsumerWorker", "kafka_enabled"]
