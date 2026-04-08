from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.field_combination import (
    FieldCombinationCreate,
    FieldCombinationResponse,
    FieldCombinationUpdate,
)
from app.services.field_combination_service import FieldCombinationService

router = APIRouter(tags=["field-combinations"])


@router.get(
    "/campuses/{campus_id}/field-combinations",
    response_model=list[FieldCombinationResponse],
)
def list_combinations_for_campus(campus_id: int, db: Session = Depends(get_db)):
    return FieldCombinationService(db).list_by_campus(campus_id)


@router.post(
    "/campuses/{campus_id}/field-combinations",
    response_model=FieldCombinationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_combination(
    campus_id: int,
    body: FieldCombinationCreate,
    db: Session = Depends(get_db),
):
    return FieldCombinationService(db).create(campus_id, body)


@router.get("/fields/{field_id}/field-combinations", response_model=list[FieldCombinationResponse])
def list_combinations_for_field(field_id: int, db: Session = Depends(get_db)):
    return FieldCombinationService(db).list_for_field(field_id)


@router.get("/field-combinations/{combination_id}", response_model=FieldCombinationResponse)
def get_combination(combination_id: int, db: Session = Depends(get_db)):
    return FieldCombinationService(db).get(combination_id)


@router.put("/field-combinations/{combination_id}", response_model=FieldCombinationResponse)
def update_combination(
    combination_id: int,
    body: FieldCombinationUpdate,
    db: Session = Depends(get_db),
):
    return FieldCombinationService(db).update(combination_id, body)


@router.delete("/field-combinations/{combination_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_combination(combination_id: int, db: Session = Depends(get_db)):
    FieldCombinationService(db).delete(combination_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
