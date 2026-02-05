from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas import BusinessLegalCreate, BusinessLegalResponse, BusinessLegalUpdate
from app.services import BusinessLegalService

router = APIRouter(tags=["business-legal"])


@router.get("/businesses/{business_id}/legal", response_model=BusinessLegalResponse)
def get_legal_by_business_id(business_id: int, db: Session = Depends(get_db)):
    service = BusinessLegalService(db)
    return service.get_legal_by_business_id(business_id)


@router.post(
    "/businesses/{business_id}/legal",
    response_model=BusinessLegalResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_legal(
    business_id: int, legal_in: BusinessLegalCreate, db: Session = Depends(get_db)
):
    service = BusinessLegalService(db)
    return service.create_legal(business_id, legal_in)


@router.put("/businesses/{business_id}/legal", response_model=BusinessLegalResponse)
def update_legal(
    business_id: int, legal_in: BusinessLegalUpdate, db: Session = Depends(get_db)
):
    service = BusinessLegalService(db)
    return service.update_legal_by_business_id(business_id, legal_in)


@router.delete("/businesses/{business_id}/legal", status_code=status.HTTP_204_NO_CONTENT)
def delete_legal(business_id: int, db: Session = Depends(get_db)):
    service = BusinessLegalService(db)
    service.delete_legal_by_business_id(business_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
