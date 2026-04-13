"""Pydantic schemas for payment method configuration."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PaymentMethodsBase(BaseModel):
    id_business: int = Field(..., ge=1)
    id_campus: int = Field(..., ge=1)

    uses_cash: bool = False

    uses_yape: bool = False
    yape_phone: Optional[str] = Field(None, max_length=20)
    yape_qr_url: Optional[str] = None

    uses_plin: bool = False
    plin_phone: Optional[str] = Field(None, max_length=20)
    plin_qr_url: Optional[str] = None

    uses_bank_transfer: bool = False
    bank_name: Optional[str] = Field(None, max_length=100)
    account_currency: Optional[str] = Field(None, max_length=10)
    account_number: Optional[str] = Field(None, max_length=50)
    cci: Optional[str] = Field(None, max_length=50)
    account_holder_name: Optional[str] = Field(None, max_length=200)
    account_holder_doc: Optional[str] = Field(None, max_length=30)

    uses_card: bool = False
    card_provider: Optional[str] = Field(None, max_length=60)
    merchant_id: Optional[str] = Field(None, max_length=100)
    terminal_id: Optional[str] = Field(None, max_length=100)
    public_key: Optional[str] = Field(None, max_length=200)

    uses_pos: bool = False
    pos_provider: Optional[str] = Field(None, max_length=60)
    pos_detail: Optional[str] = None

    uses_apple_pay: bool = False
    apple_pay_provider: Optional[str] = Field(None, max_length=60)
    apple_pay_merchant_id: Optional[str] = Field(None, max_length=120)

    uses_google_pay: bool = False
    google_pay_provider: Optional[str] = Field(None, max_length=60)
    google_pay_merchant_id: Optional[str] = Field(None, max_length=120)

    uses_invoice: bool = False
    invoice_detail: Optional[str] = None

    extra: Optional[dict[str, Any]] = None
    status: str = Field(default="active", max_length=30)

    @field_validator(
        "yape_phone",
        "yape_qr_url",
        "plin_phone",
        "plin_qr_url",
        "bank_name",
        "account_currency",
        "account_number",
        "cci",
        "account_holder_name",
        "account_holder_doc",
        "card_provider",
        "merchant_id",
        "terminal_id",
        "public_key",
        "pos_provider",
        "pos_detail",
        "apple_pay_provider",
        "apple_pay_merchant_id",
        "google_pay_provider",
        "google_pay_merchant_id",
        "invoice_detail",
        "status",
        mode="before",
    )
    @classmethod
    def _strip_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def _validate_dependencies(self) -> "PaymentMethodsBase":
        requirements = {
            "uses_yape": ["yape_phone", "yape_qr_url"],
            "uses_plin": ["plin_phone", "plin_qr_url"],
            "uses_bank_transfer": [
                "bank_name",
                "account_currency",
                "account_number",
                "cci",
                "account_holder_name",
                "account_holder_doc",
            ],
            "uses_card": ["card_provider", "merchant_id", "terminal_id", "public_key"],
            "uses_pos": ["pos_provider", "pos_detail"],
            "uses_apple_pay": ["apple_pay_provider", "apple_pay_merchant_id"],
            "uses_google_pay": ["google_pay_provider", "google_pay_merchant_id"],
            "uses_invoice": ["invoice_detail"],
        }

        for method_flag, required_fields in requirements.items():
            if not getattr(self, method_flag):
                continue

            missing_fields = [
                field_name
                for field_name in required_fields
                if getattr(self, field_name) in (None, "")
            ]
            if missing_fields:
                raise ValueError(
                    f"{', '.join(missing_fields)} are required when {method_flag} is true"
                )
        return self


class PaymentMethodsCreate(PaymentMethodsBase):
    pass


class PaymentMethodsUpdate(BaseModel):
    id_business: Optional[int] = Field(None, ge=1)
    id_campus: Optional[int] = Field(None, ge=1)

    uses_cash: Optional[bool] = None

    uses_yape: Optional[bool] = None
    yape_phone: Optional[str] = Field(None, max_length=20)
    yape_qr_url: Optional[str] = None

    uses_plin: Optional[bool] = None
    plin_phone: Optional[str] = Field(None, max_length=20)
    plin_qr_url: Optional[str] = None

    uses_bank_transfer: Optional[bool] = None
    bank_name: Optional[str] = Field(None, max_length=100)
    account_currency: Optional[str] = Field(None, max_length=10)
    account_number: Optional[str] = Field(None, max_length=50)
    cci: Optional[str] = Field(None, max_length=50)
    account_holder_name: Optional[str] = Field(None, max_length=200)
    account_holder_doc: Optional[str] = Field(None, max_length=30)

    uses_card: Optional[bool] = None
    card_provider: Optional[str] = Field(None, max_length=60)
    merchant_id: Optional[str] = Field(None, max_length=100)
    terminal_id: Optional[str] = Field(None, max_length=100)
    public_key: Optional[str] = Field(None, max_length=200)

    uses_pos: Optional[bool] = None
    pos_provider: Optional[str] = Field(None, max_length=60)
    pos_detail: Optional[str] = None

    uses_apple_pay: Optional[bool] = None
    apple_pay_provider: Optional[str] = Field(None, max_length=60)
    apple_pay_merchant_id: Optional[str] = Field(None, max_length=120)

    uses_google_pay: Optional[bool] = None
    google_pay_provider: Optional[str] = Field(None, max_length=60)
    google_pay_merchant_id: Optional[str] = Field(None, max_length=120)

    uses_invoice: Optional[bool] = None
    invoice_detail: Optional[str] = None

    extra: Optional[dict[str, Any]] = None
    status: Optional[str] = Field(None, max_length=30)

    @field_validator(
        "yape_phone",
        "yape_qr_url",
        "plin_phone",
        "plin_qr_url",
        "bank_name",
        "account_currency",
        "account_number",
        "cci",
        "account_holder_name",
        "account_holder_doc",
        "card_provider",
        "merchant_id",
        "terminal_id",
        "public_key",
        "pos_provider",
        "pos_detail",
        "apple_pay_provider",
        "apple_pay_merchant_id",
        "google_pay_provider",
        "google_pay_merchant_id",
        "invoice_detail",
        "status",
        mode="before",
    )
    @classmethod
    def _strip_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class PaymentMethodsResponse(PaymentMethodsBase):
    model_config = ConfigDict(from_attributes=True)

    id_payment_methods: int
    created_at: datetime
    updated_at: datetime


__all__ = [
    "PaymentMethodsBase",
    "PaymentMethodsCreate",
    "PaymentMethodsUpdate",
    "PaymentMethodsResponse",
]
