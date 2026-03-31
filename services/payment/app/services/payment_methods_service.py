"""Business logic for payment method configuration CRUD."""

from __future__ import annotations

from typing import Optional

import logging

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.error_codes import PAYMENT_METHODS_NOT_FOUND, http_error
from app.domain.payment.methods import (
    current_state,
    map_integrity_error,
    validate_method_requirements,
)
from app.repository import payment_methods_repository
from app.schemas.payment_methods import PaymentMethodsCreate, PaymentMethodsUpdate

logger = logging.getLogger(__name__)


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
            raise http_error(
                PAYMENT_METHODS_NOT_FOUND,
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
            raise http_error(
                PAYMENT_METHODS_EXISTS,
                detail="Payment methods configuration already exists for this business/campus",
            )

        validate_method_requirements(data)
        try:
            return payment_methods_repository.create_payment_methods(self.db, data)
        except IntegrityError as exc:
            self.db.rollback()
            raise map_integrity_error(exc) from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.exception(
                "Failed to create payment methods. id_business=%s id_campus=%s",
                data.get("id_business"),
                data.get("id_campus"),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create payment methods configuration",
            ) from exc

    def update_payment_methods(self, payment_methods_id: int, payload: PaymentMethodsUpdate):
        payment_methods = self.get_payment_methods(payment_methods_id)
        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            return payment_methods

        merged_data = current_state(payment_methods)
        merged_data.update(update_data)
        validate_method_requirements(merged_data)

        for field, value in update_data.items():
            setattr(payment_methods, field, value)

        try:
            return payment_methods_repository.save_payment_methods(self.db, payment_methods)
        except IntegrityError as exc:
            self.db.rollback()
            raise map_integrity_error(exc) from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.exception(
                "Failed to update payment methods. id_payment_methods=%s",
                payment_methods_id,
            )
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
            logger.exception(
                "Failed to delete payment methods. id_payment_methods=%s",
                payment_methods_id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete payment methods configuration",
            ) from exc

__all__ = ["PaymentMethodsService"]
