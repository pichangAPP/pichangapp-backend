from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.error_codes import (
    BOOKING_BAD_REQUEST,
    BOOKING_INTERNAL_ERROR,
    BOOKING_SERVICE_UNAVAILABLE,
    BUSINESS_NOT_FOUND,
    http_error,
)
from app.integrations import auth_reader
from app.models import Business
from app.repository import business_repository
from app.schemas import (
    BusinessCreate,
    BusinessProfileResponse,
    BusinessResponse,
    BusinessUpdate,
    CampusResponse,
)
from app.services.campus_service import (
    build_campus_entity,
    populate_available_schedules,
    validate_campus_fields,
)
from app.services.location_utils import haversine_distance


class BusinessService:
    def __init__(self, db: Session):
        self.db = db

    def list_businesses(self) -> list[Business]:
        try:
            businesses = business_repository.list_businesses(self.db)
            self._attach_manager_data(businesses)
            return businesses
        except SQLAlchemyError as exc:  
            raise http_error(
                BOOKING_INTERNAL_ERROR,
                detail="Failed to list businesses",
            ) from exc

    def list_businesses_by_location(
        self, latitude: float, longitude: float
    ) -> list[BusinessResponse]:
        try:
            businesses = business_repository.list_businesses(self.db)
            self._attach_manager_data(businesses)
        except SQLAlchemyError as exc:
            raise http_error(
                BOOKING_INTERNAL_ERROR,
                detail="Failed to list businesses",
            ) from exc


        # For each business we locate the nearest campus (if coords exist),
        # keep the campuses sorted by proximity, then rank all businesses
        business_distances: list[tuple[float, BusinessResponse]] = []
        for business in businesses:
            populate_available_schedules(self.db, business.campuses)
            campuses_with_coords = [
                campus
                for campus in business.campuses
                if campus.coords_x is not None and campus.coords_y is not None
            ]

            if not campuses_with_coords:
                continue

            campus_responses_with_distance: list[tuple[float, CampusResponse]] = []
            for campus in campuses_with_coords:
                distance = haversine_distance(
                    latitude,
                    longitude,
                    float(campus.coords_x),
                    float(campus.coords_y),
                )
                campus_response = CampusResponse.model_validate(campus)
                campus_responses_with_distance.append((distance, campus_response))

            campus_responses_with_distance.sort(key=lambda item: item[0])
            ordered_campuses = [campus for _, campus in campus_responses_with_distance]

            business_response = BusinessResponse.model_validate(business).model_copy(
                update={"campuses": ordered_campuses}
            )
            nearest_distance = campus_responses_with_distance[0][0]
            business_distances.append((nearest_distance, business_response))

        business_distances.sort(key=lambda item: item[0])
        return [business for _, business in business_distances]

    def get_business(self, business_id: int) -> Business:
        business = business_repository.get_business(self.db, business_id)
        if not business:
            raise http_error(
                BUSINESS_NOT_FOUND,
                detail=f"Business {business_id} not found",
            )
        populate_available_schedules(self.db, business.campuses)
        self._attach_manager_data([business])
        return business

    def get_business_profile(self, business_id: int) -> BusinessProfileResponse:
        business = business_repository.get_business_profile(self.db, business_id)
        if not business:
            raise http_error(
                BUSINESS_NOT_FOUND,
                detail=f"Business {business_id} not found",
            )
        return BusinessProfileResponse.model_validate(business)

    def get_business_by_manager(self, manager_id: int) -> Business:
        business = business_repository.get_business_by_manager(self.db, manager_id)
        if not business:
            raise http_error(
                BUSINESS_NOT_FOUND,
                detail=f"Business for manager {manager_id} not found",
            )
        populate_available_schedules(self.db, business.campuses)
        self._attach_manager_data([business])
        return business

    def create_business(self, business_in: BusinessCreate) -> Business:
        try:
            business = Business(**business_in.model_dump(exclude={"campuses"}))
            for campus_in in business_in.campuses:
                validate_campus_fields(self.db, campus_in)
                business.campuses.append(build_campus_entity(campus_in))
            
            self._validate_business_entity(business)
            business_repository.create_business(self.db, business)
            self.db.commit()
            self.db.refresh(business)
            self._attach_manager_data([business])
            return business
        except SQLAlchemyError as exc:
            self.db.rollback()
            print(f"SQLAlchemy error: {exc}")  # o usa logging
            raise http_error(
                BOOKING_INTERNAL_ERROR,
                detail=f"Failed to create business: {exc}",
            ) from exc

    def update_business(self, business_id: int, business_in: BusinessUpdate) -> Business:
        business = self.get_business(business_id)
        update_data = business_in.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(business, field, value)
        business.updated_at = datetime.now(timezone.utc)

        self._validate_business_entity(business)

        try:
            self.db.flush()
            self.db.commit()
            self.db.refresh(business)
            self._attach_manager_data([business])
            return business
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise http_error(
                BOOKING_INTERNAL_ERROR,
                detail="Failed to update business",
            ) from exc

    def delete_business(self, business_id: int) -> None:
        business = self.get_business(business_id)
        try:
            business_repository.delete_business(self.db, business)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise http_error(
                BOOKING_INTERNAL_ERROR,
                detail="Failed to delete business",
            ) from exc

    def _validate_business_entity(self, business: Business) -> None:
        if business.min_price is not None and float(business.min_price) < 0:
            raise http_error(
                BOOKING_BAD_REQUEST,
                detail="min_price must be zero or greater",
            )

    def _attach_manager_data(self, businesses: list[Business]) -> None:
        business_list = [business for business in businesses if business is not None]
        if not business_list:
            return

        manager_ids: set[int] = set()
        for business in business_list:
            if business.id_manager is not None:
                manager_ids.add(business.id_manager)
            for campus in getattr(business, "campuses", []) or []:
                if campus.id_manager is not None:
                    manager_ids.add(campus.id_manager)

        try:
            managers = auth_reader.get_manager_summaries(self.db, manager_ids)
        except auth_reader.AuthReaderError as exc:
            raise http_error(
                BOOKING_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

        for business in business_list:
            manager_id = business.id_manager
            business.manager = managers.get(manager_id) if manager_id else None  # type: ignore[attr-defined]
            for campus in getattr(business, "campuses", []) or []:
                campus_manager_id = campus.id_manager
                campus.manager = (  # type: ignore[attr-defined]
                    managers.get(campus_manager_id) if campus_manager_id else None
                )
