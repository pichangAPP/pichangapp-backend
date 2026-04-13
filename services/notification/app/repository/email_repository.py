"""Repository responsible for sending emails through SMTP."""

from __future__ import annotations

import smtplib
from email import encoders
from email.message import EmailMessage, Message
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from app.core.config import Settings, settings
from app.models import EmailAttachment, EmailContent


class EmailRepository:
    """Handles the low level communication with the SMTP server."""

    def __init__(self, config: Settings | None = None):
        self._settings = config or settings

    def _headers_from(self, email: EmailContent) -> tuple[str, str, str]:
        if not self._settings.SMTP_FROM_EMAIL:
            raise RuntimeError("SMTP_FROM_EMAIL must be configured to send emails")
        if self._settings.SMTP_FROM_NAME:
            from_header = formataddr(
                (self._settings.SMTP_FROM_NAME, self._settings.SMTP_FROM_EMAIL)
            )
        else:
            from_header = self._settings.SMTP_FROM_EMAIL
        to_header = ", ".join(email.recipients)
        return from_header, to_header, email.subject

    def _build_message_simple(self, email: EmailContent) -> EmailMessage:
        """Correo sin imágenes inline (solo adjuntos normales)."""
        message = EmailMessage()
        from_h, to_h, subj = self._headers_from(email)
        message["Subject"] = subj
        message["From"] = from_h
        message["To"] = to_h
        if email.reply_to:
            message["Reply-To"] = email.reply_to

        text_body = email.text_body or "Este correo requiere un cliente compatible con HTML."
        message.set_content(text_body)
        message.add_alternative(email.html_body, subtype="html")

        for attachment in email.attachments:
            if attachment.content_id:
                continue
            maintype, subtype = attachment.content_type.split("/", 1)
            message.add_attachment(
                attachment.data,
                maintype=maintype,
                subtype=subtype,
                filename=attachment.filename,
            )
        return message

    def _mime_inline_image(self, attachment: EmailAttachment) -> MIMEImage:
        _, subtype = attachment.content_type.split("/", 1)
        part = MIMEImage(attachment.data, _subtype=subtype)
        cid = attachment.content_id or ""
        if cid and not cid.startswith("<"):
            cid = f"<{cid}>"
        part.add_header("Content-ID", cid)
        part.add_header("Content-Disposition", "inline", filename=attachment.filename)
        return part

    def _mime_binary_attachment(self, attachment: EmailAttachment) -> MIMEBase:
        maintype, subtype = attachment.content_type.split("/", 1)
        part = MIMEBase(maintype, subtype)
        part.set_payload(attachment.data)
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=attachment.filename,
        )
        return part

    def _build_message_with_inline(self, email: EmailContent) -> Message:
        """multipart/mixed: alternative(related(html + inline)) + adjuntos."""
        inline = [a for a in email.attachments if a.content_id]
        regular = [a for a in email.attachments if not a.content_id]

        root = MIMEMultipart("mixed")
        from_h, to_h, subj = self._headers_from(email)
        root["Subject"] = subj
        root["From"] = from_h
        root["To"] = to_h
        if email.reply_to:
            root["Reply-To"] = email.reply_to

        text_body = email.text_body or "Este correo requiere un cliente compatible con HTML."
        alt_outer = MIMEMultipart("alternative")
        alt_outer.attach(MIMEText(text_body, "plain", "utf-8"))

        related = MIMEMultipart("related")
        related.attach(MIMEText(email.html_body, "html", "utf-8"))
        for att in inline:
            related.attach(self._mime_inline_image(att))
        alt_outer.attach(related)
        root.attach(alt_outer)

        for att in regular:
            root.attach(self._mime_binary_attachment(att))

        return root

    def _build_message(self, email: EmailContent) -> Message:
        if any(a.content_id for a in email.attachments):
            return self._build_message_with_inline(email)
        return self._build_message_simple(email)

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
