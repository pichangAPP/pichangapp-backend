"""Notification payload creation and publishing for rent events."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from decimal import Decimal
from email.utils import parseaddr
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.kafka import build_event, publish_event
from app.integrations import auth_reader, booking_reader
from app.domain.rent.hydrator import ordered_schedules_for_rent
from app.models.rent import Rent
from app.repository import rent_repository

logger = logging.getLogger(__name__)


class RentNotificationPublisher:
    """Build and publish rent notification events."""

    _EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    def __init__(self, db: Session):
        """Initialize with a DB session for lookups.

        Used by: RentService update flows to publish Kafka notifications.
        """
        self.db = db

    @staticmethod
    def _datetime_to_iso(value: Optional[datetime]) -> Optional[str]:
        """Convert datetimes to ISO strings for payloads.

        Used by: build_payload.
        """
        if value is None:
            return None
        return value.isoformat()

    @staticmethod
    def _decimal_to_str(value: Optional[Decimal]) -> Optional[str]:
        """Convert decimals to string for payloads.

        Used by: build_payload.
        """
        if value is None:
            return None
        return format(value, "f")

    @classmethod
    def _is_valid_email(cls, value: Optional[str]) -> bool:
        """Check if a string is a valid email address.

        Used by: build_payload to guard notification recipients.
        """
        if not value:
            return False
        _, addr = parseaddr(value)
        if addr != value:
            return False
        return bool(cls._EMAIL_REGEX.match(value))

    @staticmethod
    def _split_full_name(full_name: Optional[str]) -> tuple[str, str]:
        """Split a full name into name/lastname components.

        Used by: build_payload when no user record exists.
        """
        if not full_name:
            return "", ""
        parts = full_name.strip().split()
        if not parts:
            return "", ""
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], " ".join(parts[1:])

    def build_payload(self, rent: Rent) -> Optional[Dict[str, object]]:
        """Assemble the full notification payload for a rent.

        Used by: publish before emitting Kafka events.
        """
        ordered = ordered_schedules_for_rent(self.db, rent)
        if not ordered:
            logger.info(
                "Skipping notification payload creation for rent %s due to missing schedule data",
                rent.id_rent,
            )
            return None

        schedule = ordered[0]
        if schedule.id_field is None:
            logger.info(
                "Skipping notification payload creation for rent %s due to missing schedule data",
                rent.id_rent,
            )
            return None

        field_names: list[str] = []
        for sch in ordered:
            if sch.id_field is None:
                continue
            fsum = booking_reader.get_field_summary(self.db, sch.id_field)
            if fsum is not None:
                field_names.append(fsum.field_name)

        field = booking_reader.get_field_summary(self.db, schedule.id_field)
        if field is None:
            logger.info(
                "Skipping notification payload creation for rent %s due to missing external data",
                rent.id_rent,
            )
            return None

        wait_minutes: List[Decimal] = []
        for sch in ordered:
            if sch.id_field is None:
                continue
            fsum = booking_reader.get_field_summary(self.db, sch.id_field)
            if fsum is not None:
                wait_minutes.append(fsum.minutes_wait)
        minutes_wait = max(wait_minutes) if wait_minutes else field.minutes_wait

        if schedule.id_user is not None:
            try:
                user = auth_reader.get_user_summary(self.db, schedule.id_user)
            except auth_reader.AuthReaderError as exc:
                logger.warning(
                    "Auth service unavailable while building notification payload: %s",
                    exc,
                )
                return None
            if user is None:
                logger.info(
                    "Skipping notification payload creation for rent %s due to missing user data",
                    rent.id_rent,
                )
                return None
            if not self._is_valid_email(user.email):
                logger.info(
                    "Skipping notification payload creation for rent %s due to invalid user email",
                    rent.id_rent,
                )
                return None
            user_payload = {
                "name": user.name,
                "lastname": user.lastname,
                "email": user.email,
            }
        else:
            if not self._is_valid_email(rent.customer_email):
                logger.info(
                    "Skipping notification payload creation for rent %s due to invalid customer email",
                    rent.id_rent,
                )
                return None
            name, lastname = self._split_full_name(rent.customer_full_name)
            user_payload = {
                "name": name or "Cliente",
                "lastname": lastname,
                "email": rent.customer_email,
            }

        campus = booking_reader.get_campus_summary(self.db, field.id_campus)
        if campus is None:
            logger.info(
                "Skipping notification payload creation for rent %s because campus information is missing",
                rent.id_rent,
            )
            return None

        campus_payload = {
            "id_campus": campus.id_campus,
            "name": campus.name,
            "address": campus.address,
            "district": campus.district,
            "contact_email": campus.email_contact,
            "contact_phone": campus.phone_contact,
        }

        manager_payload = None
        if campus.id_manager is not None:
            try:
                manager = auth_reader.get_user_summary(self.db, campus.id_manager)
            except auth_reader.AuthReaderError as exc:
                logger.warning(
                    "Auth service unavailable while fetching manager for rent %s: %s",
                    rent.id_rent,
                    exc,
                )
                manager = None
        else:
            manager = None
        if manager is not None and manager.email:
            manager_payload = {
                "name": manager.name,
                "lastname": manager.lastname,
                "email": manager.email,
            }

        display_field_name = (
            ", ".join(field_names) if len(field_names) > 1 else (field_names[0] if field_names else field.field_name)
        )
        payload: Dict[str, object] = {
            "rent": {
                "rent_id": rent.id_rent,
                "schedule_day": schedule.day_of_week,
                "start_time": self._datetime_to_iso(rent.start_time),
                "end_time": self._datetime_to_iso(rent.end_time),
                "status": rent.status,
                "period": rent.period,
                "mount": self._decimal_to_str(rent.mount),
                "payment_deadline": self._datetime_to_iso(rent.payment_deadline),
                "field_name": display_field_name,
                "field_names": field_names,
                "minutes_wait": self._decimal_to_str(minutes_wait),
                "campus": campus_payload,
            },
            "user": {
                "name": user_payload["name"],
                "lastname": user_payload["lastname"],
                "email": user_payload["email"],
            },
            "manager": manager_payload,
        }
        if schedule.id_user is not None:
            payload["id_user"] = schedule.id_user
        return payload

    def publish(self, *, rent: Rent, event_type: str) -> None:
        """Publish a notification event to Kafka with the full payload.

        Used by: RentService update flows (payment_received/verdict).
        """
        payload = self.build_payload(rent)
        if payload is None:
            return
        event = build_event(
            event_type=event_type,
            payload={"notification": payload},
        )
        logger.info("Publishing notification event %s for rent %s", event_type, rent.id_rent)
        publish_event(event, key=str(rent.id_rent))

    @classmethod
    def publish_by_id(cls, *, rent_id: int, event_type: str) -> None:
        """Fetch rent data and publish a notification in a new DB session.

        Used by: BackgroundTasks in RentService.
        """
        db = SessionLocal()
        try:
            rent = rent_repository.get_rent(db, rent_id)
            if rent is None:
                return
            service = cls(db)
            service.publish(rent=rent, event_type=event_type)
        finally:
            db.close()

    @classmethod
    def publish_events_by_id(cls, *, rent_id: int, event_types: list[str]) -> None:
        """Publish multiple notification events with a single DB session.

        Used by: RentService when multiple events must be emitted in background.
        """
        if not event_types:
            return
        db = SessionLocal()
        try:
            rent = rent_repository.get_rent(db, rent_id)
            if rent is None:
                return
            service = cls(db)
            for event_type in event_types:
                service.publish(rent=rent, event_type=event_type)
        finally:
            db.close()


__all__ = ["RentNotificationPublisher"]
