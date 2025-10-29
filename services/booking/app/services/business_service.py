from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Business
from app.repository import business_repository
from app.schemas import BusinessCreate, BusinessResponse, BusinessUpdate, CampusResponse
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
            return business_repository.list_businesses(self.db)
        except SQLAlchemyError as exc:  
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to list businesses",
            ) from exc

    def list_businesses_by_location(
        self, latitude: float, longitude: float
    ) -> list[BusinessResponse]:
        try:
            businesses = business_repository.list_businesses(self.db)
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to list businesses",
            ) from exc


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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Business {business_id} not found",
            )
        populate_available_schedules(self.db, business.campuses)
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
            return business
        except SQLAlchemyError as exc:
            self.db.rollback()
            print(f"SQLAlchemy error: {exc}")  # o usa logging
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create business: {exc}"
            ) from exc

    def update_business(self, business_id: int, business_in: BusinessUpdate) -> Business:
        business = self.get_business(business_id)
        update_data = business_in.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(business, field, value)

        self._validate_business_entity(business)

        try:
            self.db.flush()
            self.db.commit()
            self.db.refresh(business)
            return business
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update business",
            ) from exc

    def delete_business(self, business_id: int) -> None:
        business = self.get_business(business_id)
        try:
            business_repository.delete_business(self.db, business)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete business",
            ) from exc

    def _validate_business_entity(self, business: Business) -> None:
        if business.min_price is not None and float(business.min_price) < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="min_price must be zero or greater",
            )