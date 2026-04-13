from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class BusinessLegalBase(BaseModel):
    terms_and_conditions: Optional[str] = None
    terms_url: Optional[str] = None
    privacy_policy: Optional[str] = None
    privacy_policy_url: Optional[str] = None
    cookies_policy: Optional[str] = None
    cookies_policy_url: Optional[str] = None
    refund_policy: Optional[str] = None
    refund_policy_url: Optional[str] = None

    version: Optional[str] = None
    effective_from: Optional[date] = None
    last_reviewed_at: Optional[date] = None

    @field_validator(
        "terms_and_conditions",
        "terms_url",
        "privacy_policy",
        "privacy_policy_url",
        "cookies_policy",
        "cookies_policy_url",
        "refund_policy",
        "refund_policy_url",
        "version",
        mode="before",
    )
    @classmethod
    def _strip_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class BusinessLegalCreate(BusinessLegalBase):
    pass


class BusinessLegalUpdate(BaseModel):
    terms_and_conditions: Optional[str] = None
    terms_url: Optional[str] = None
    privacy_policy: Optional[str] = None
    privacy_policy_url: Optional[str] = None
    cookies_policy: Optional[str] = None
    cookies_policy_url: Optional[str] = None
    refund_policy: Optional[str] = None
    refund_policy_url: Optional[str] = None

    version: Optional[str] = None
    effective_from: Optional[date] = None
    last_reviewed_at: Optional[date] = None

    @field_validator(
        "terms_and_conditions",
        "terms_url",
        "privacy_policy",
        "privacy_policy_url",
        "cookies_policy",
        "cookies_policy_url",
        "refund_policy",
        "refund_policy_url",
        "version",
        mode="before",
    )
    @classmethod
    def _strip_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class BusinessLegalResponse(BusinessLegalBase):
    model_config = ConfigDict(from_attributes=True)

    id_business_legal: int
    id_business: int
    created_at: datetime
    updated_at: datetime
