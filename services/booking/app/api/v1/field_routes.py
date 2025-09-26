from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas import FieldCreate, FieldResponse, FieldUpdate
from app.services import FieldService

router = APIRouter(tags=["fields"])


@router.get("/campuses/{campus_id}/fields", response_model=list[FieldResponse])
def list_fields(campus_id: int, db: Session = Depends(get_db)):
    service = FieldService(db)
    return service.list_fields(campus_id)


@router.post(
    "/campuses/{campus_id}/fields",
    response_model=FieldResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_field(campus_id: int, field_in: FieldCreate, db: Session = Depends(get_db)):
    service = FieldService(db)
    return service.create_field(campus_id, field_in)


@router.get("/fields/{field_id}", response_model=FieldResponse)
def get_field(field_id: int, db: Session = Depends(get_db)):
    service = FieldService(db)
    return service.get_field(field_id)


@router.put("/fields/{field_id}", response_model=FieldResponse)
def update_field(field_id: int, field_in: FieldUpdate, db: Session = Depends(get_db)):
    service = FieldService(db)
    return service.update_field(field_id, field_in)


@router.delete("/fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_field(field_id: int, db: Session = Depends(get_db)):
    service = FieldService(db)
    service.delete_field(field_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
