"""Repository responsible for sending emails through SMTP."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from app.core.config import Settings, settings
from app.models import EmailContent


class EmailRepository:
    """Handles the low level communication with the SMTP server."""

    def __init__(self, config: Settings | None = None):
        self._settings = config or settings

    def _build_message(self, email: EmailContent) -> EmailMessage:
        message = EmailMessage()
        message["Subject"] = email.subject

        if not self._settings.SMTP_FROM_EMAIL:
            raise RuntimeError("SMTP_FROM_EMAIL must be configured to send emails")

        if self._settings.SMTP_FROM_NAME:
            message["From"] = formataddr(
                (self._settings.SMTP_FROM_NAME, self._settings.SMTP_FROM_EMAIL)
            )
        else:
            message["From"] = self._settings.SMTP_FROM_EMAIL

        message["To"] = ", ".join(email.recipients)

        if email.reply_to:
            message["Reply-To"] = email.reply_to

        text_body = email.text_body or "Este correo requiere un cliente compatible con HTML."
        message.set_content(text_body)
        message.add_alternative(email.html_body, subtype="html")

        for attachment in email.attachments:
            maintype, subtype = attachment.content_type.split("/", 1)
            message.add_attachment(
                attachment.data,
                maintype=maintype,
                subtype=subtype,
                filename=attachment.filename,
            )

        return message

    def _login(self, client: smtplib.SMTP) -> None:
        username = self._settings.SMTP_USERNAME
        password = self._settings.SMTP_PASSWORD
        if username and password:
            client.login(username, password)

    def send_email(self, email: EmailContent) -> None:
        if not self._settings.SMTP_HOST:
            raise RuntimeError("SMTP_HOST must be configured to send emails")

        message = self._build_message(email)

        try:
            if self._settings.SMTP_USE_SSL:
                with smtplib.SMTP_SSL(
                    self._settings.SMTP_HOST,
                    self._settings.SMTP_PORT,
                    timeout=self._settings.SMTP_TIMEOUT,
                ) as client:
                    self._login(client)
                    client.send_message(message)
            else:
                with smtplib.SMTP(
                    self._settings.SMTP_HOST,
                    self._settings.SMTP_PORT,
                    timeout=self._settings.SMTP_TIMEOUT,
                ) as client:
                    if self._settings.SMTP_USE_TLS:
                        client.starttls()
                    self._login(client)
                    client.send_message(message)
        except smtplib.SMTPException as exc:  # pragma: no cover - network dependent
            raise RuntimeError("Failed to deliver email") from exc


__all__ = ["EmailRepository"]
