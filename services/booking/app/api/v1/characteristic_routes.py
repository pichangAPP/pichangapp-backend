from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas import CharacteristicResponse, CharacteristicUpdate
from app.services import CharacteristicService

router = APIRouter(prefix="/campuses/{campus_id}/characteristic", tags=["characteristics"])


@router.get("", response_model=CharacteristicResponse)
def get_characteristic(campus_id: int, db: Session = Depends(get_db)):
    service = CharacteristicService(db)
    return service.get_characteristic(campus_id)


@router.patch("", response_model=CharacteristicResponse)
def update_characteristic(
    campus_id: int, characteristic_in: CharacteristicUpdate, db: Session = Depends(get_db)
):
    service = CharacteristicService(db)
    return service.update_characteristic(campus_id, characteristic_in)
