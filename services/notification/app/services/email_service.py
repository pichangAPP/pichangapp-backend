"""High level email orchestration for the notification service."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

from app.models import EmailAttachment, EmailContent
from app.repository import EmailRepository
from app.schemas import NotificationRequest
from app.domain.notification.attachments import (
    build_pass_link,
    build_qr_attachment,
    build_reservation_pass,
    upload_pass_to_firebase,
)
from app.domain.notification.branding import BRAND_LOGO_CONTENT_ID, get_brand_logo_bytes
from app.domain.notification.context import build_common_context
from app.domain.notification.templates import (
    build_manager_subject,
    build_user_subject,
    select_manager_templates,
    select_user_templates,
)

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

    def _build_common_context(self, payload: NotificationRequest) -> Dict[str, Any]:
        return build_common_context(payload)

    def _with_email_extras(self, context: Dict[str, Any], *, pass_link: str) -> Dict[str, Any]:
        merged = dict(context)
        merged["pass_link"] = pass_link
        # Gmail suele bloquear data: URLs en <img>; usamos adjunto inline (CID) en el repositorio.
        merged["brand_logo_src"] = (
            f"cid:{BRAND_LOGO_CONTENT_ID}" if get_brand_logo_bytes() else ""
        )
        return merged

    @staticmethod
    def _logo_inline_attachments() -> list[EmailAttachment]:
        raw = get_brand_logo_bytes()
        if not raw:
            return []
        return [
            EmailAttachment(
                filename="cuadra-logo.png",
                content_type="image/png",
                data=raw,
                content_id=BRAND_LOGO_CONTENT_ID,
            )
        ]

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
        attachments: Sequence[EmailAttachment] | None = None,
    ) -> EmailContent:
        html_body = self._render_template(html_template, context)
        text_body = self._render_template(text_template, context)
        return EmailContent(
            subject=subject,
            recipients=[recipient],
            html_body=html_body,
            text_body=text_body,
            attachments=tuple(attachments or ()),
        )

    @staticmethod
    def _is_rejected_status(status_value: str) -> bool:
        return (status_value or "").strip().lower().startswith("rejected_")

    def send_rent_notification(self, payload: NotificationRequest) -> None:
        """Send the rent confirmation emails for manager and user."""

        base_context = self._build_common_context(payload)
        pass_link = build_pass_link(payload, firebase_url=None)
        context = self._with_email_extras(base_context, pass_link=pass_link)

        user_html, user_text = select_user_templates(payload.rent.status)
        include_pass_assets = not self._is_rejected_status(payload.rent.status)
        user_attachments = [*self._logo_inline_attachments()]
        reservation_pass = None
        if include_pass_assets:
            reservation_pass = build_reservation_pass(payload, pass_link=pass_link)
            upload_pass_to_firebase(attachment=reservation_pass, payload=payload)
            user_qr = build_qr_attachment(
                pass_link,
                f"reserva-{payload.rent.rent_id}-usuario",
            )
            user_attachments.extend([reservation_pass, user_qr])
        user_email = self._build_email(
            subject=build_user_subject(payload.rent.status),
            recipient=payload.user.email,
            html_template=user_html,
            text_template=user_text,
            context=context,
            attachments=user_attachments,
        )
        if payload.manager is None:
            self._repository.send_email(user_email)
            logger.info(
                "Reservation receipt sent to %s for rent %s",
                user_email.primary_recipient(),
                payload.rent.rent_id,
            )
            logger.info(
                "No campus manager configured for campus %s; skipping manager email",
                payload.rent.campus.id_campus,
            )
            return

        manager_context = self._with_email_extras(dict(context), pass_link=pass_link)
        manager_context["recipient"] = payload.manager
        manager_html, manager_text = select_manager_templates(payload.rent.status)

        manager_attachments = [*self._logo_inline_attachments()]
        if include_pass_assets and reservation_pass is not None:
            manager_qr = build_qr_attachment(
                pass_link,
                f"reserva-{payload.rent.rent_id}-administrador",
            )
            manager_attachments.extend([reservation_pass, manager_qr])
        manager_email = self._build_email(
            subject=build_manager_subject(payload.rent.status),
            recipient=payload.manager.email,
            html_template=manager_html,
            text_template=manager_text,
            context=manager_context,
            attachments=manager_attachments,
        )

        def _send(content) -> None:
            self._repository.send_email(content)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = (
                pool.submit(_send, user_email),
                pool.submit(_send, manager_email),
            )
            for fut in as_completed(futures):
                fut.result()

        logger.info(
            "Reservation receipt sent to %s for rent %s",
            user_email.primary_recipient(),
            payload.rent.rent_id,
        )
        logger.info(
            "Reservation confirmation sent to manager %s for rent %s",
            manager_email.primary_recipient(),
            payload.rent.rent_id,
        )

    def send_user_confirmation(self, payload: NotificationRequest) -> None:
        """Send a reservation confirmation email only to the user."""

        base_context = self._build_common_context(payload)
        pass_link = build_pass_link(payload, firebase_url=None)
        context = self._with_email_extras(base_context, pass_link=pass_link)

        user_html, user_text = select_user_templates(payload.rent.status)
        include_pass_assets = not self._is_rejected_status(payload.rent.status)
        user_attachments = [*self._logo_inline_attachments()]
        if include_pass_assets:
            reservation_pass = build_reservation_pass(payload, pass_link=pass_link)
            upload_pass_to_firebase(attachment=reservation_pass, payload=payload)
            user_qr = build_qr_attachment(
                pass_link,
                f"reserva-{payload.rent.rent_id}-usuario",
            )
            user_attachments.extend([reservation_pass, user_qr])
        user_email = self._build_email(
            subject=build_user_subject(payload.rent.status),
            recipient=payload.user.email,
            html_template=user_html,
            text_template=user_text,
            context=context,
            attachments=user_attachments,
        )
        self._repository.send_email(user_email)
        logger.info(
            "Reservation confirmation sent to user %s for rent %s",
            user_email.primary_recipient(),
            payload.rent.rent_id,
        )


__all__ = ["EmailService"]
