"""API routes for managing rents."""

from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Query, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.rent import (
    RentCancelRequest,
    RentCancelResponse,
    RentAdminCreate,
    RentAdminUpdate,
    RentCreate,
    RentCreateCombo,
    RentPaymentResponse,
    RentResponse,
    RentUpdate,
)
from app.services.rent_service import RentService

router = APIRouter(prefix="/rents", tags=["rents"])


@router.get("", response_model=List[RentResponse])
def list_rents(
    *,
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None, description="Filter rents by status"),
    exclude_status: Optional[str] = Query(
        None,
        description="Omit rents whose status equals this value (e.g. cancelled)",
    ),
    schedule_id: Optional[int] = Query(None, description="Filter rents by schedule id"),
) -> List[RentResponse]:
    """Retrieve all rents optionally filtered by status or schedule."""

    service = RentService(db)
    rents = service.list_rents(
        status_filter=status,
        exclude_status=exclude_status,
        schedule_id=schedule_id,
    )
    return rents


@router.get("/fields/{field_id}", response_model=List[RentResponse])
def list_rents_by_field(
    field_id: int,
    *,
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None, description="Filter rents by status"),
    exclude_status: Optional[str] = Query(
        None,
        description="Omit rents whose status equals this value (e.g. cancelled)",
    ),
) -> List[RentResponse]:
    """Retrieve rents associated with a specific field."""

    service = RentService(db)
    return service.list_rents_by_field(
        field_id,
        status_filter=status,
        exclude_status=exclude_status,
    )


@router.get("/users/{user_id}", response_model=List[RentResponse])
def list_rents_by_user(
    user_id: int,
    *,
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None, description="Filter rents by status"),
    exclude_status: Optional[str] = Query(
        None,
        description="Omit rents whose status equals this value (e.g. cancelled)",
    ),
) -> List[RentResponse]:
    """Retrieve rents associated with a specific user."""

    service = RentService(db)
    return service.list_rents_by_user(
        user_id,
        status_filter=status,
        exclude_status=exclude_status,
    )


@router.get("/campus/{campus_id}", response_model=List[RentResponse])
def list_rents_by_campus(
    campus_id: int,
    *,
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None, description="Filter rents by status"),
    exclude_status: Optional[str] = Query(
        None,
        description="Omit rents whose status equals this value (e.g. cancelled)",
    ),
) -> List[RentResponse]:
    """Retrieve rents associated with a specific campus."""

    service = RentService(db)
    return service.list_rents_by_campus(
        campus_id,
        status_filter=status,
        exclude_status=exclude_status,
    )


@router.get("/users/{user_id}/history", response_model=List[RentResponse])
def list_user_rent_history(
    user_id: int,
    *,
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None, description="Filter rents by status"),
    exclude_status: Optional[str] = Query(
        None,
        description="Omit rents whose status equals this value (e.g. cancelled)",
    ),
) -> List[RentResponse]:
    """Retrieve the rent history for a specific user ordered from newest to oldest."""

    service = RentService(db)
    return service.list_user_rent_history(
        user_id,
        status_filter=status,
        exclude_status=exclude_status,
    )


@router.get("/{rent_id}", response_model=RentResponse)
def get_rent(rent_id: int, db: Session = Depends(get_db)) -> RentResponse:
    """Retrieve a rent by its identifier."""

    service = RentService(db)
    return service.get_rent(rent_id)


@router.post("", response_model=RentPaymentResponse, status_code=status.HTTP_201_CREATED)
def create_rent(
    payload: RentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> RentPaymentResponse:
    """Create a new rent."""

    service = RentService(db)
    return service.create_rent(payload, background_tasks=background_tasks)


@router.post("/combo", response_model=RentPaymentResponse, status_code=status.HTTP_201_CREATED)
def create_rent_combo(
    payload: RentCreateCombo,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> RentPaymentResponse:
    """Create a rent that spans multiple fields (combined courts)."""

    service = RentService(db)
    return service.create_rent_combo(payload, background_tasks=background_tasks)


@router.post("/admin", response_model=RentResponse, status_code=status.HTTP_201_CREATED)
def create_rent_admin(
    payload: RentAdminCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> RentResponse:
    """Create a new rent by admin."""

    service = RentService(db)
    return service.create_rent_admin(payload, background_tasks=background_tasks)


@router.put("/{rent_id}/cancel", response_model=RentCancelResponse)
def cancel_rent(
    rent_id: int,
    payload: RentCancelRequest = Body(default=RentCancelRequest()),
    db: Session = Depends(get_db),
) -> RentCancelResponse:
    """Cancel a rent and set the schedule available."""

    service = RentService(db)
    return service.cancel_rent(rent_id, payload)


@router.put("/{rent_id}", response_model=RentResponse)
def update_rent(
    rent_id: int,
    payload: RentUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> RentResponse:
    """Update an existing rent."""

    service = RentService(db)
    return service.update_rent(
        rent_id,
        payload,
        background_tasks=background_tasks,
    )


@router.put("/admin/{rent_id}", response_model=RentResponse)
def update_rent_admin(
    rent_id: int,
    payload: RentAdminUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> RentResponse:
    """Update an existing rent by admin."""

    service = RentService(db)
    return service.update_rent_admin(
        rent_id,
        payload,
        background_tasks=background_tasks,
    )


@router.delete("/{rent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rent(rent_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a rent."""

    service = RentService(db)
    service.delete_rent(rent_id)
