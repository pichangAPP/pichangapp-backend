"""API routes for payment operations."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.payment import PaymentCreate, PaymentResponse, PaymentUpdate
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/", response_model=List[PaymentResponse])
def list_payments(
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
) -> List[PaymentResponse]:
    service = PaymentService(db)
    return service.list_payments(status_filter=status_filter)


@router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment(payment_id: int, db: Session = Depends(get_db)) -> PaymentResponse:
    service = PaymentService(db)
    return service.get_payment(payment_id)


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=PaymentResponse,
)
def create_payment(payload: PaymentCreate, db: Session = Depends(get_db)) -> PaymentResponse:
    service = PaymentService(db)
    return service.create_payment(payload)


@router.patch("/{payment_id}", response_model=PaymentResponse)
def update_payment(
    payment_id: int,
    payload: PaymentUpdate,
    db: Session = Depends(get_db),
) -> PaymentResponse:
    service = PaymentService(db)
    return service.update_payment(payment_id, payload)


__all__ = ["router"]
