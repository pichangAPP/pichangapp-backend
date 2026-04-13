from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.error_codes import (
    BOOKING_INTERNAL_ERROR,
    CAMPUS_NOT_FOUND,
    http_error,
)
from app.domain.business.validations import get_business_or_error
from app.domain.campus import (
    attach_campus_manager_data,
    build_campus_entity,
    populate_available_schedules,
    sync_campus_images,
    validate_campus_entity,
    validate_campus_fields,
)
from app.models import Campus, Characteristic
from app.repository import campus_repository
from app.schemas import CampusCreate, CampusUpdate
from app.services.location_utils import haversine_distance
    
class CampusService:
    def __init__(self, db: Session):
        self.db = db

    def list_campuses(self, business_id: int) -> list[Campus]:
        get_business_or_error(self.db, business_id)
        try:
            campuses = campus_repository.list_campuses_by_business(self.db, business_id)
            populate_available_schedules(self.db, campuses)
            attach_campus_manager_data(self.db, campuses)
            return campuses
        except SQLAlchemyError as exc:  # pragma: no cover - defensive
            raise http_error(
                BOOKING_INTERNAL_ERROR,
                detail="Failed to list campuses",
            ) from exc

    def list_campuses_by_location(
        self, business_id: int, latitude: float, longitude: float
    ) -> list[Campus]:
        campuses = self.list_campuses(business_id)

        campuses_with_distance: list[tuple[float, Campus]] = []
        campuses_without_coordinates: list[Campus] = []

        for campus in campuses:
            if campus.coords_x is None or campus.coords_y is None:
                campuses_without_coordinates.append(campus)
                continue

            distance = haversine_distance(
                latitude, longitude, float(campus.coords_x), float(campus.coords_y)
            )
            campuses_with_distance.append((distance, campus))

        campuses_with_distance.sort(key=lambda item: item[0])

        ordered_campuses = [campus for _, campus in campuses_with_distance]
        ordered_campuses.extend(campuses_without_coordinates)

        return ordered_campuses

    def get_campus(self, campus_id: int) -> Campus:
        campus = campus_repository.get_campus(self.db, campus_id)
        if not campus:
            raise http_error(
                CAMPUS_NOT_FOUND,
                detail=f"Campus {campus_id} not found",
            )
        populate_available_schedules(self.db, [campus])
        attach_campus_manager_data(self.db, [campus])
        return campus

    def create_campus(self, business_id: int, campus_in: CampusCreate) -> Campus:
        business = get_business_or_error(self.db, business_id)
        
        validate_campus_fields(self.db, campus_in)
        campus = build_campus_entity(campus_in)
        campus.business = business
        validate_campus_entity(campus)

        try:
            campus_repository.create_campus(self.db, campus)
            self.db.commit()
            self.db.refresh(campus)
            attach_campus_manager_data(self.db, [campus])
            return campus
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise http_error(
                BOOKING_INTERNAL_ERROR,
                detail="Failed to create campus",
            ) from exc

    def update_campus(self, campus_id: int, campus_in: CampusUpdate) -> Campus:
        campus = self.get_campus(campus_id)
        print("Campus before update:", campus)
        update_data = campus_in.model_dump(exclude_unset=True)
        images_data = update_data.pop("images", None)
        characteristic_data = update_data.pop("characteristic", None)

        for field, value in update_data.items():
            setattr(campus, field, value)

        if characteristic_data is not None:
            if not campus.characteristic:
                campus.characteristic = Characteristic(**characteristic_data)
            else:
                for field, value in characteristic_data.items():
                    setattr(campus.characteristic, field, value)

        if images_data is not None:
            sync_campus_images(self.db, campus, images_data)

        campus.updated_at = datetime.now(timezone.utc)
        validate_campus_entity(campus)
        try:
            self.db.flush()
            self.db.commit()
            self.db.refresh(campus)
            attach_campus_manager_data(self.db, [campus])
            return campus
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise http_error(
                BOOKING_INTERNAL_ERROR,
                detail=f"Failed to update campus {exc}",
            ) from exc

    def delete_campus(self, campus_id: int) -> None:
        campus = self.get_campus(campus_id)
        try:
            campus_repository.delete_campus(self.db, campus)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise http_error(
                BOOKING_INTERNAL_ERROR,
                detail="Failed to delete campus",
            ) from exc
    
