from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.rent import Rent
from app.models.schedule import Schedule
from app.schemas.rent import RentCreate, RentUpdate


class RentService:

    def __init__(self, db: Session):
        self.db = db

    def list_rents(
        self,
        *,
        status_filter: Optional[str] = None,
        schedule_id: Optional[int] = None,
    ) -> List[Rent]:

        query = self.db.query(Rent)

        if status_filter is not None:
            query = query.filter(Rent.status == status_filter)
        if schedule_id is not None:
            query = query.filter(Rent.id_schedule == schedule_id)

        return query.order_by(Rent.start_time).all()

    def get_rent(self, rent_id: int) -> Rent:

        rent = self.db.query(Rent).filter(Rent.id_rent == rent_id).first()
        if rent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rent not found",
            )
        return rent

    def _ensure_schedule_exists(self, schedule_id: int) -> None:

        schedule_exists = (
            self.db.query(Schedule)
            .filter(Schedule.id_schedule == schedule_id)
            .first()
        )
        if schedule_exists is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated schedule not found",
            )

    def create_rent(self, payload: RentCreate) -> Rent:

        self._ensure_schedule_exists(payload.id_schedule)
        rent = Rent(**payload.dict())
        self.db.add(rent)
        self.db.commit()
        self.db.refresh(rent)
        return rent

    def update_rent(self, rent_id: int, payload: RentUpdate) -> Rent:
        """Update an existing rent."""

        rent = self.get_rent(rent_id)

        update_data = payload.dict(exclude_unset=True)
        if "id_schedule" in update_data:
            self._ensure_schedule_exists(update_data["id_schedule"])

        for field, value in update_data.items():
            setattr(rent, field, value)

        self.db.commit()
        self.db.refresh(rent)
        return rent

    def delete_rent(self, rent_id: int) -> None:
        """Delete a rent from the database."""

        rent = self.get_rent(rent_id)
        self.db.delete(rent)
        self.db.commit()
