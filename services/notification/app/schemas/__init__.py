"""Pydantic schemas used by the notification service."""

from app.schemas.email import (
    CampusSummary,
    NotificationRequest,
    Person,
    RentDetails,
)

__all__ = ["NotificationRequest", "Person", "RentDetails", "CampusSummary"]
