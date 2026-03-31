from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.status_catalog import StatusCatalog
from app.repository import status_catalog_repository
from app.schemas.status_catalog import (
    StatusCatalogCreate,
    StatusCatalogResponse,
    StatusCatalogUpdate,
)
from app.core.error_codes import STATUS_NOT_FOUND, http_error


class StatusCatalogService:
    def __init__(self, db: Session):
        self.db = db

    def list_statuses(
        self,
        *,
        entity: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[StatusCatalogResponse]:
        statuses = status_catalog_repository.list_statuses(
            self.db,
            entity=entity,
            is_active=is_active,
        )
        return [self._build_status_response(status_item) for status_item in statuses]

    def get_status(self, status_id: int) -> StatusCatalogResponse:
        status_item = status_catalog_repository.get_status(self.db, status_id)
        if status_item is None:
            raise http_error(
                STATUS_NOT_FOUND,
                detail="Status not found",
            )
        return self._build_status_response(status_item)

    def create_status(self, payload: StatusCatalogCreate) -> StatusCatalogResponse:
        existing = status_catalog_repository.get_status_by_entity_code(
            self.db,
            entity=payload.entity,
            code=payload.code,
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Status code already exists for this entity",
            )
        status_item = status_catalog_repository.create_status(
            self.db, payload.model_dump()
        )
        return self._build_status_response(status_item)

    def update_status(
        self,
        status_id: int,
        payload: StatusCatalogUpdate,
    ) -> StatusCatalogResponse:
        status_item = status_catalog_repository.get_status(self.db, status_id)
        if status_item is None:
            raise http_error(
                STATUS_NOT_FOUND,
                detail="Status not found",
            )

        update_data = payload.model_dump(exclude_unset=True)
        if "entity" in update_data or "code" in update_data:
            entity = update_data.get("entity", status_item.entity)
            code = update_data.get("code", status_item.code)
            existing = status_catalog_repository.get_status_by_entity_code(
                self.db,
                entity=entity,
                code=code,
                exclude_status_id=status_id,
            )
            if existing is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Status code already exists for this entity",
                )

        for attribute, value in update_data.items():
            setattr(status_item, attribute, value)

        status_catalog_repository.save_status(self.db, status_item)
        return self._build_status_response(status_item)

    def delete_status(self, status_id: int) -> None:
        status_item = status_catalog_repository.get_status(self.db, status_id)
        if status_item is None:
            raise http_error(
                STATUS_NOT_FOUND,
                detail="Status not found",
            )
        status_catalog_repository.delete_status(self.db, status_item)

    @staticmethod
    def _build_status_response(status_item: StatusCatalog) -> StatusCatalogResponse:
        return StatusCatalogResponse(
            id_status=status_item.id_status,
            entity=status_item.entity,
            code=status_item.code,
            name=status_item.name,
            description=status_item.description,
            is_final=status_item.is_final,
            sort_order=status_item.sort_order,
            is_active=status_item.is_active,
            created_at=status_item.created_at,
            updated_at=status_item.updated_at,
        )
