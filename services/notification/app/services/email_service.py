"""High level email orchestration for the notification service."""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

from app.core.config import settings
from app.models import EmailContent
from app.repository import EmailRepository
from app.schemas import NotificationRequest

logger = logging.getLogger(__name__)


class EmailService:
    """Render templates and deliver emails for reservation notifications."""

    def __init__(
        self,
        *,
        repository: EmailRepository | None = None,
        templates_path: Optional[Path] = None,
    ):
        self._repository = repository or EmailRepository()
        self._templates_path = templates_path or Path(__file__).resolve().parent.parent / "templates"
        self._environment = Environment(
            loader=FileSystemLoader(self._templates_path),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        if value.tzinfo:
            return value.strftime("%d/%m/%Y %H:%M %Z")
        return value.strftime("%d/%m/%Y %H:%M")

    @staticmethod
    def _format_decimal(value: Decimal) -> str:
        return f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")

    def _build_common_context(self, payload: NotificationRequest) -> Dict[str, Any]:
        rent = payload.rent
        campus = rent.campus
        context: Dict[str, Any] = {
            "rent": rent,
            "user": payload.user,
            "manager": payload.manager,
            "campus": campus,
            "field_name": rent.field_name,
            "date_range": f"{self._format_datetime(rent.start_time)} - {self._format_datetime(rent.end_time)}",
            "start_time_display": self._format_datetime(rent.start_time),
            "end_time_display": self._format_datetime(rent.end_time),
            "payment_deadline_display": self._format_datetime(rent.payment_deadline),
            "amount_display": self._format_decimal(rent.mount),
        }
        return context

    def _render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        try:
            template = self._environment.get_template(template_name)
        except TemplateNotFound as exc:  # pragma: no cover - configuration error
            raise RuntimeError(f"Email template '{template_name}' not found") from exc
        return template.render(**context)

    def _build_email(
        self,
        *,
        subject: str,
        recipient: str,
        html_template: str,
        text_template: str,
        context: Dict[str, Any],
    ) -> EmailContent:
        html_body = self._render_template(html_template, context)
        text_body = self._render_template(text_template, context)
        return EmailContent(
            subject=subject,
            recipients=[recipient],
            html_body=html_body,
            text_body=text_body,
        )

    def send_rent_notification(self, payload: NotificationRequest) -> None:
        """Send the rent confirmation emails for manager and user."""

        context = self._build_common_context(payload)

        user_email = self._build_email(
            subject=settings.USER_RECEIPT_SUBJECT,
            recipient=payload.user.email,
            html_template="user_receipt.html",
            text_template="user_receipt.txt",
            context=context,
        )
        self._repository.send_email(user_email)
        logger.info(
            "Reservation receipt sent to %s for rent %s",
            user_email.primary_recipient(),
            payload.rent.rent_id,
        )

        if payload.manager is None:
            logger.info(
                "No campus manager configured for campus %s; skipping manager email",
                payload.rent.campus.id_campus,
            )
            return

        manager_context = dict(context)
        manager_context["recipient"] = payload.manager

        manager_email = self._build_email(
            subject=settings.MANAGER_CONFIRMATION_SUBJECT,
            recipient=payload.manager.email,
            html_template="manager_confirmation.html",
            text_template="manager_confirmation.txt",
            context=manager_context,
        )
        self._repository.send_email(manager_email)
        logger.info(
            "Reservation confirmation sent to manager %s for rent %s",
            manager_email.primary_recipient(),
            payload.rent.rent_id,
        )


__all__ = ["EmailService"]
