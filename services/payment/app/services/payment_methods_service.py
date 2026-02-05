"""Business logic for payment method configuration CRUD."""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.repository import payment_methods_repository
from app.schemas.payment_methods import PaymentMethodsCreate, PaymentMethodsUpdate


class PaymentMethodsService:
    def __init__(self, db: Session):
        self.db = db

    def list_payment_methods(
        self,
        *,
        id_business: Optional[int] = None,
        id_campus: Optional[int] = None,
        status_filter: Optional[str] = None,
    ):
        return payment_methods_repository.list_payment_methods(
            self.db,
            id_business=id_business,
            id_campus=id_campus,
            status_filter=status_filter,
        )

    def get_payment_methods(self, payment_methods_id: int):
        payment_methods = payment_methods_repository.get_payment_methods(
            self.db, payment_methods_id
        )
        if payment_methods is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment methods configuration not found",
            )
        return payment_methods

    def create_payment_methods(self, payload: PaymentMethodsCreate):
        data = payload.model_dump(exclude_unset=True)
        existing = payment_methods_repository.get_payment_methods_by_business_campus(
            self.db,
            id_business=data["id_business"],
            id_campus=data["id_campus"],
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment methods configuration already exists for this business/campus",
            )

        self._validate_method_requirements(data)
        try:
            return payment_methods_repository.create_payment_methods(self.db, data)
        except IntegrityError as exc:
            self.db.rollback()
            raise self._map_integrity_error(exc) from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create payment methods configuration",
            ) from exc

    def update_payment_methods(self, payment_methods_id: int, payload: PaymentMethodsUpdate):
        payment_methods = self.get_payment_methods(payment_methods_id)
        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            return payment_methods

        merged_data = self._current_state(payment_methods)
        merged_data.update(update_data)
        self._validate_method_requirements(merged_data)

        for field, value in update_data.items():
            setattr(payment_methods, field, value)

        try:
            return payment_methods_repository.save_payment_methods(self.db, payment_methods)
        except IntegrityError as exc:
            self.db.rollback()
            raise self._map_integrity_error(exc) from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update payment methods configuration",
            ) from exc

    def delete_payment_methods(self, payment_methods_id: int) -> None:
        payment_methods = self.get_payment_methods(payment_methods_id)
        try:
            payment_methods_repository.delete_payment_methods(self.db, payment_methods)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete payment methods configuration",
            ) from exc

    @staticmethod
    def _validate_method_requirements(data: dict) -> None:
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
            if not data.get(method_flag):
                continue

            missing_fields = [
                field_name
                for field_name in required_fields
                if data.get(field_name) in (None, "")
            ]
            if missing_fields:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"{', '.join(missing_fields)} are required when "
                        f"{method_flag} is true"
                    ),
                )

    @staticmethod
    def _current_state(payment_methods) -> dict:
        return {
            "id_business": payment_methods.id_business,
            "id_campus": payment_methods.id_campus,
            "uses_cash": payment_methods.uses_cash,
            "uses_yape": payment_methods.uses_yape,
            "yape_phone": payment_methods.yape_phone,
            "yape_qr_url": payment_methods.yape_qr_url,
            "uses_plin": payment_methods.uses_plin,
            "plin_phone": payment_methods.plin_phone,
            "plin_qr_url": payment_methods.plin_qr_url,
            "uses_bank_transfer": payment_methods.uses_bank_transfer,
            "bank_name": payment_methods.bank_name,
            "account_currency": payment_methods.account_currency,
            "account_number": payment_methods.account_number,
            "cci": payment_methods.cci,
            "account_holder_name": payment_methods.account_holder_name,
            "account_holder_doc": payment_methods.account_holder_doc,
            "uses_card": payment_methods.uses_card,
            "card_provider": payment_methods.card_provider,
            "merchant_id": payment_methods.merchant_id,
            "terminal_id": payment_methods.terminal_id,
            "public_key": payment_methods.public_key,
            "uses_pos": payment_methods.uses_pos,
            "pos_provider": payment_methods.pos_provider,
            "pos_detail": payment_methods.pos_detail,
            "uses_apple_pay": payment_methods.uses_apple_pay,
            "apple_pay_provider": payment_methods.apple_pay_provider,
            "apple_pay_merchant_id": payment_methods.apple_pay_merchant_id,
            "uses_google_pay": payment_methods.uses_google_pay,
            "google_pay_provider": payment_methods.google_pay_provider,
            "google_pay_merchant_id": payment_methods.google_pay_merchant_id,
            "uses_invoice": payment_methods.uses_invoice,
            "invoice_detail": payment_methods.invoice_detail,
            "extra": payment_methods.extra,
            "status": payment_methods.status,
        }

    @staticmethod
    def _map_integrity_error(exc: IntegrityError) -> HTTPException:
        detail = str(exc.orig).lower()
        if "uq_payment_methods_business_campus" in detail or (
            "duplicate key value" in detail and "id_business" in detail and "id_campus" in detail
        ):
            return HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment methods configuration already exists for this business/campus",
            )

        if "chk_" in detail:
            return HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Payment methods validation failed due to check constraints",
            )

        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment methods payload",
        )


__all__ = ["PaymentMethodsService"]
