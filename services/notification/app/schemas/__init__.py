"""Pydantic schemas used by the notification service."""

from app.schemas.email import (
    BusinessRequestNotification,
    CampusSummary,
    NotificationRequest,
    Person,
    RentDetails,
)

__all__ = [
    "NotificationRequest",
    "BusinessRequestNotification",
    "Person",
    "RentDetails",
    "CampusSummary",
]
