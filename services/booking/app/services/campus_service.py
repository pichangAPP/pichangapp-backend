from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Campus, Characteristic, Field, Image
from app.repository import business_repository, campus_repository
from app.schemas import CampusCreate, CampusUpdate
from app.services.location_utils import haversine_distance


def build_campus_entity(campus_in: CampusCreate) -> Campus:
    campus_data = campus_in.model_dump(exclude={"characteristic", "fields", "images"})
    campus = Campus(**campus_data)
    characteristic = Characteristic(**campus_in.characteristic.model_dump())
    campus.characteristic = characteristic

    for field_in in campus_in.fields:
        campus.fields.append(Field(**field_in.model_dump()))
    for image_in in campus_in.images:
        campus.images.append(Image(**image_in.model_dump()))
    return campus


class CampusService:
    def __init__(self, db: Session):
        self.db = db

    def _ensure_business_exists(self, business_id: int) -> None:
        if not business_repository.get_business(self.db, business_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Business {business_id} not found",
            )

    def list_campuses(self, business_id: int) -> list[Campus]:
        self._ensure_business_exists(business_id)
        try:
            return campus_repository.list_campuses_by_business(self.db, business_id)
        except SQLAlchemyError as exc:  # pragma: no cover - defensive
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campus {campus_id} not found",
            )
        return campus

    def create_campus(self, business_id: int, campus_in: CampusCreate) -> Campus:
        business = business_repository.get_business(self.db, business_id)
        if not business:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Business {business_id} not found",
            )
        campus = build_campus_entity(campus_in)
        campus.business = business
        try:
            campus_repository.create_campus(self.db, campus)
            self.db.commit()
            self.db.refresh(campus)
            return campus
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create campus",
            ) from exc

    def update_campus(self, campus_id: int, campus_in: CampusUpdate) -> Campus:
        campus = self.get_campus(campus_id)
        update_data = campus_in.model_dump(exclude_unset=True)
        characteristic_data = update_data.pop("characteristic", None)

        for field, value in update_data.items():
            setattr(campus, field, value)

        if characteristic_data is not None:
            if not campus.characteristic:
                campus.characteristic = Characteristic(**characteristic_data)
            else:
                for field, value in characteristic_data.items():
                    setattr(campus.characteristic, field, value)
        try:
            self.db.flush()
            self.db.commit()
            self.db.refresh(campus)
            return campus
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update campus",
            ) from exc

    def delete_campus(self, campus_id: int) -> None:
        campus = self.get_campus(campus_id)
        try:
            campus_repository.delete_campus(self.db, campus)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete campus",
            ) from exc
