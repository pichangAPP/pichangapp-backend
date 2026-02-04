"""Business logic for managing payments."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.integrations import (
    AuthReaderError,
    get_payment_destination,
    get_rent_context,
    get_user_summary,
)
from app.repository import payment_repository
from app.schemas.payment import PaymentCreate, PaymentUpdate


class PaymentService:
    def __init__(self, db: Session):
        self.db = db

    def list_payments(self, *, status_filter: Optional[str] = None):
        return payment_repository.list_payments(
            self.db, status_filter=status_filter
        )

    def get_payment(self, payment_id: int):
        payment = payment_repository.get_payment(self.db, payment_id)
        if payment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found",
            )
        return payment

    def create_payment(self, payload: PaymentCreate):
        payment_data = payload.dict(exclude_unset=True)
        method = (payment_data.get("method") or "").strip().lower()

        rent_id = payment_data.pop("rent_id", None)
        payer_phone = payment_data.pop("payer_phone", None)
        approval_code = payment_data.pop("approval_code", None)

        if method in {"yape", "plin"}:
            self._apply_yape_plin_context(
                payment_data,
                rent_id=rent_id,
                payer_phone=payer_phone,
                approval_code=approval_code,
            )

        payment = payment_repository.create_payment(self.db, payment_data)
        return payment

    def update_payment(self, payment_id: int, payload: PaymentUpdate):
        payment = self.get_payment(payment_id)
        update_data = payload.dict(exclude_unset=True)

        if not update_data:
            return payment

        # Apply only the provided fields so callers can send partial updates
        # (e.g., just status/receipt) without re-sending the full object.
        for field, value in update_data.items():
            setattr(payment, field, value)

        return payment_repository.save_payment(self.db, payment)

    def _apply_yape_plin_context(
        self,
        payment_data: dict,
        *,
        rent_id: Optional[int],
        payer_phone: Optional[str],
        approval_code: Optional[str],
    ) -> None:
        if rent_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="rent_id is required for Yape/Plin payments",
            )
        if not payer_phone:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="payer_phone is required for Yape/Plin payments",
            )
        if not approval_code:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="approval_code is required for Yape/Plin payments",
            )

        rent_context = get_rent_context(self.db, rent_id)
        if rent_context is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rent not found for payment",
            )
        if rent_context.field_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Rent does not include a field identifier",
            )

        destination = get_payment_destination(self.db, rent_context.field_id)
        if destination is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Field/campus not found for payment",
            )

        receiver_phone = None
        receiver_name = None
        if destination.manager_id is not None:
            try:
                manager = get_user_summary(self.db, destination.manager_id)
            except AuthReaderError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Unable to reach auth service for campus manager",
                ) from exc

            if manager is not None and manager.phone:
                receiver_phone = manager.phone
                receiver_name = f"{manager.name} {manager.lastname}".strip()

        if not receiver_phone:
            receiver_phone = destination.business_phone
            receiver_name = receiver_name or destination.business_name

        if not receiver_phone:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No payment receiver configured for the campus",
            )

        metadata = self._merge_additional_data(
            payment_data.get("additional_data"),
            {
                "channel": payment_data.get("method"),
                "payer_phone": payer_phone,
                "approval_code": approval_code,
                "receiver_phone": receiver_phone,
                "receiver_name": receiver_name,
                "campus_id": destination.campus_id,
                "campus_name": destination.campus_name,
                "field_id": destination.field_id,
                "rent_id": rent_context.rent_id,
                "schedule_id": rent_context.schedule_id,
            },
        )

        payment_data["additional_data"] = json.dumps(metadata, ensure_ascii=True)
        if payment_data.get("reference") is None:
            payment_data["reference"] = approval_code

    @staticmethod
    def _merge_additional_data(existing: Optional[str], updates: dict) -> dict:
        if not existing:
            return dict(updates)

        try:
            payload = json.loads(existing)
        except json.JSONDecodeError:
            payload = {"client_notes": existing}

        if not isinstance(payload, dict):
            payload = {"client_notes": existing}

        payload.update(updates)
        return payload


__all__ = ["PaymentService"]
