"""API routes for managing status catalog entries."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.status_catalog import (
    StatusCatalogCreate,
    StatusCatalogResponse,
    StatusCatalogUpdate,
)
from app.services.status_catalog_service import StatusCatalogService


router = APIRouter(prefix="/status-catalog", tags=["status-catalog"])


@router.get("", response_model=List[StatusCatalogResponse])
def list_statuses(
    *,
    db: Session = Depends(get_db),
    entity: Optional[str] = Query(None, description="Filter by entity"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
) -> List[StatusCatalogResponse]:
    """Retrieve all statuses optionally filtered by entity or active flag."""

    service = StatusCatalogService(db)
    return service.list_statuses(entity=entity, is_active=is_active)


@router.get("/{status_id}", response_model=StatusCatalogResponse)
def get_status(status_id: int, db: Session = Depends(get_db)) -> StatusCatalogResponse:
    """Retrieve a status catalog entry by its identifier."""

    service = StatusCatalogService(db)
    return service.get_status(status_id)


@router.post("", response_model=StatusCatalogResponse, status_code=status.HTTP_201_CREATED)
def create_status(
    payload: StatusCatalogCreate,
    db: Session = Depends(get_db),
) -> StatusCatalogResponse:
    """Create a new status catalog entry."""

    service = StatusCatalogService(db)
    return service.create_status(payload)


@router.put("/{status_id}", response_model=StatusCatalogResponse)
def update_status(
    status_id: int,
    payload: StatusCatalogUpdate,
    db: Session = Depends(get_db),
) -> StatusCatalogResponse:
    """Update an existing status catalog entry."""

    service = StatusCatalogService(db)
    return service.update_status(status_id, payload)


@router.delete("/{status_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_status(status_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a status catalog entry."""

    service = StatusCatalogService(db)
    service.delete_status(status_id)
