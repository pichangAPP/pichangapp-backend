"""Email related domain models."""

from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass(frozen=True)
class EmailContent:
    """Represents an email ready to be delivered."""

    subject: str
    recipients: Sequence[str]
    html_body: str
    text_body: Optional[str] = None
    reply_to: Optional[str] = None

    def primary_recipient(self) -> str:
        """Return the first recipient address or an empty string."""
        return self.recipients[0] if self.recipients else ""


__all__ = ["EmailContent"]
