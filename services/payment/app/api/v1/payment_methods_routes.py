"""API routes for payment methods configuration CRUD."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.payment_methods import (
    PaymentMethodsCreate,
    PaymentMethodsResponse,
    PaymentMethodsUpdate,
)
from app.services.payment_methods_service import PaymentMethodsService

router = APIRouter(prefix="/payment-methods", tags=["payment-methods"])


@router.get("/", response_model=list[PaymentMethodsResponse])
def list_payment_methods(
    id_business: Optional[int] = None,
    id_campus: Optional[int] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[PaymentMethodsResponse]:
    service = PaymentMethodsService(db)
    return service.list_payment_methods(
        id_business=id_business,
        id_campus=id_campus,
        status_filter=status_filter,
    )


@router.get("/{payment_methods_id}", response_model=PaymentMethodsResponse)
def get_payment_methods(
    payment_methods_id: int, db: Session = Depends(get_db)
) -> PaymentMethodsResponse:
    service = PaymentMethodsService(db)
    return service.get_payment_methods(payment_methods_id)


@router.post("/", response_model=PaymentMethodsResponse, status_code=status.HTTP_201_CREATED)
def create_payment_methods(
    payload: PaymentMethodsCreate, db: Session = Depends(get_db)
) -> PaymentMethodsResponse:
    service = PaymentMethodsService(db)
    return service.create_payment_methods(payload)


@router.patch("/{payment_methods_id}", response_model=PaymentMethodsResponse)
def update_payment_methods(
    payment_methods_id: int,
    payload: PaymentMethodsUpdate,
    db: Session = Depends(get_db),
) -> PaymentMethodsResponse:
    service = PaymentMethodsService(db)
    return service.update_payment_methods(payment_methods_id, payload)


@router.delete("/{payment_methods_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payment_methods(payment_methods_id: int, db: Session = Depends(get_db)) -> Response:
    service = PaymentMethodsService(db)
    service.delete_payment_methods(payment_methods_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
