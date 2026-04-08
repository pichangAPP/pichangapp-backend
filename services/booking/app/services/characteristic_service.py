from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.error_codes import BOOKING_INTERNAL_ERROR, http_error
from app.models import Characteristic
from app.schemas import CharacteristicUpdate
from app.services.campus_service import CampusService


class CharacteristicService:
    def __init__(self, db: Session):
        self.db = db
        self.campus_service = CampusService(db)

    def get_characteristic(self, campus_id: int) -> Characteristic:
        campus = self.campus_service.get_campus(campus_id)
        return campus.characteristic

    def update_characteristic(
        self, campus_id: int, characteristic_in: CharacteristicUpdate
    ) -> Characteristic:
        characteristic = self.get_characteristic(campus_id)
        update_data = characteristic_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(characteristic, field, value)
        try:
            self.db.flush()
            self.db.commit()
            self.db.refresh(characteristic)
            return characteristic
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise http_error(
                BOOKING_INTERNAL_ERROR,
                detail="Failed to update characteristic",
            ) from exc
