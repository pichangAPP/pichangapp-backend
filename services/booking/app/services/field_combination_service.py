from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.error_codes import FIELD_NOT_FOUND, http_error
from app.models.field_combination import FieldCombination, FieldCombinationMember
from app.repository import field_combination_repository, field_repository
from app.schemas.field_combination import (
    FieldCombinationCreate,
    FieldCombinationMemberResponse,
    FieldCombinationResponse,
    FieldCombinationUpdate,
)
from app.services.campus_service import CampusService


class FieldCombinationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.campus_service = CampusService(db)

    def _to_response(self, combo: FieldCombination) -> FieldCombinationResponse:
        members_out = [
            FieldCombinationMemberResponse(
                id_field=m.id_field,
                field_name=m.field.field_name if m.field else "",
                sort_order=m.sort_order,
            )
            for m in sorted(combo.members, key=lambda x: (x.sort_order, x.id_field))
        ]
        return FieldCombinationResponse(
            id_combination=combo.id_combination,
            id_campus=combo.id_campus,
            name=combo.name,
            description=combo.description,
            status=combo.status,
            price_per_hour=combo.price_per_hour,
            created_at=combo.created_at,
            updated_at=combo.updated_at,
            members=members_out,
        )

    def _validate_members_for_campus(
        self,
        campus_id: int,
        members_payload: list,
    ) -> None:
        field_ids = [m.id_field for m in members_payload]
        if len(field_ids) != len(set(field_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate field in combination",
            )
        for mid in field_ids:
            field = field_repository.get_field(self.db, mid)
            if field is None:
                raise http_error(FIELD_NOT_FOUND, detail=f"Field {mid} not found")
            if field.id_campus != campus_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Field {mid} does not belong to this campus",
                )

    def list_by_campus(self, campus_id: int) -> list[FieldCombinationResponse]:
        self.campus_service.get_campus(campus_id)
        combos = field_combination_repository.list_combinations_by_campus(
            self.db, campus_id, active_only=False
        )
        return [self._to_response(c) for c in combos]

    def list_for_field(self, field_id: int) -> list[FieldCombinationResponse]:
        field = field_repository.get_field(self.db, field_id)
        if field is None:
            raise http_error(FIELD_NOT_FOUND, detail="Field not found")
        combos = field_combination_repository.list_combinations_containing_field(
            self.db, field_id, active_only=True
        )
        return [self._to_response(c) for c in combos]

    def get(self, combination_id: int) -> FieldCombinationResponse:
        combo = field_combination_repository.get_combination(self.db, combination_id)
        if combo is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Combination not found")
        return self._to_response(combo)

    def create(self, campus_id: int, payload: FieldCombinationCreate) -> FieldCombinationResponse:
        self.campus_service.get_campus(campus_id)
        self._validate_members_for_campus(campus_id, payload.members)

        combo = FieldCombination(
            id_campus=campus_id,
            name=payload.name,
            description=payload.description,
            status=payload.status,
            price_per_hour=payload.price_per_hour,
        )
        for m in payload.members:
            combo.members.append(
                FieldCombinationMember(
                    id_field=m.id_field,
                    sort_order=m.sort_order,
                )
            )
        field_combination_repository.create_combination(self.db, combo)
        loaded = field_combination_repository.get_combination(self.db, combo.id_combination)
        assert loaded is not None
        return self._to_response(loaded)

    def update(self, combination_id: int, payload: FieldCombinationUpdate) -> FieldCombinationResponse:
        combo = field_combination_repository.get_combination(self.db, combination_id)
        if combo is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Combination not found")

        if payload.name is not None:
            combo.name = payload.name
        if payload.description is not None:
            combo.description = payload.description
        if payload.status is not None:
            combo.status = payload.status
        if payload.price_per_hour is not None:
            combo.price_per_hour = payload.price_per_hour

        if payload.members is not None:
            self._validate_members_for_campus(combo.id_campus, payload.members)
            combo.members.clear()
            for m in payload.members:
                combo.members.append(
                    FieldCombinationMember(
                        id_field=m.id_field,
                        sort_order=m.sort_order,
                    )
                )

        combo.updated_at = datetime.now(timezone.utc)
        field_combination_repository.save_combination(self.db, combo)
        loaded = field_combination_repository.get_combination(self.db, combination_id)
        assert loaded is not None
        return self._to_response(loaded)

    def delete(self, combination_id: int) -> None:
        combo = field_combination_repository.get_combination(self.db, combination_id)
        if combo is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Combination not found")
        field_combination_repository.delete_combination(self.db, combo)
