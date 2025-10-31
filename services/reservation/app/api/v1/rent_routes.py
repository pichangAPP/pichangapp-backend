"""API routes for managing rents."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.rent import RentCreate, RentResponse, RentUpdate
from app.services.rent_service import RentService

router = APIRouter(prefix="/rents", tags=["rents"])


@router.get("/", response_model=List[RentResponse])
def list_rents(
    *,
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None, description="Filter rents by status"),
    schedule_id: Optional[int] = Query(None, description="Filter rents by schedule id"),
) -> List[RentResponse]:
    """Retrieve all rents optionally filtered by status or schedule."""

    service = RentService(db)
    rents = service.list_rents(status_filter=status, schedule_id=schedule_id)
    return rents


@router.get("/fields/{field_id}", response_model=List[RentResponse])
def list_rents_by_field(
    field_id: int,
    *,
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None, description="Filter rents by status"),
) -> List[RentResponse]:
    """Retrieve rents associated with a specific field."""

    service = RentService(db)
    return service.list_rents_by_field(field_id, status_filter=status)


@router.get("/users/{user_id}", response_model=List[RentResponse])
def list_rents_by_user(
    user_id: int,
    *,
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None, description="Filter rents by status"),
) -> List[RentResponse]:
    """Retrieve rents associated with a specific user."""

    service = RentService(db)
    return service.list_rents_by_user(user_id, status_filter=status)


@router.get("/users/{user_id}/history", response_model=List[RentResponse])
def list_user_rent_history(
    user_id: int,
    *,
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None, description="Filter rents by status"),
) -> List[RentResponse]:
    """Retrieve the rent history for a specific user ordered from newest to oldest."""

    service = RentService(db)
    return service.list_user_rent_history(user_id, status_filter=status)


@router.get("/{rent_id}", response_model=RentResponse)
def get_rent(rent_id: int, db: Session = Depends(get_db)) -> RentResponse:
    """Retrieve a rent by its identifier."""

    service = RentService(db)
    return service.get_rent(rent_id)


@router.post("/", response_model=RentResponse, status_code=status.HTTP_201_CREATED)
def create_rent(payload: RentCreate, db: Session = Depends(get_db)) -> RentResponse:
    """Create a new rent."""

    service = RentService(db)
    return service.create_rent(payload)


@router.put("/{rent_id}", response_model=RentResponse)
def update_rent(
    rent_id: int,
    payload: RentUpdate,
    db: Session = Depends(get_db),
) -> RentResponse:
    """Update an existing rent."""

    service = RentService(db)
    return service.update_rent(rent_id, payload)


@router.delete("/{rent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rent(rent_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a rent."""

    service = RentService(db)
    service.delete_rent(rent_id)
