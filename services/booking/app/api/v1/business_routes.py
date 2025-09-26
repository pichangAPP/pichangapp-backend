from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas import BusinessCreate, BusinessResponse, BusinessUpdate
from app.services import BusinessService

router = APIRouter(prefix="/businesses", tags=["businesses"])


@router.get("", response_model=list[BusinessResponse])
def list_businesses(db: Session = Depends(get_db)):
    service = BusinessService(db)
    return service.list_businesses()


@router.post("", response_model=BusinessResponse, status_code=status.HTTP_201_CREATED)
def create_business(business_in: BusinessCreate, db: Session = Depends(get_db)):
    service = BusinessService(db)
    return service.create_business(business_in)


@router.get("/{business_id}", response_model=BusinessResponse)
def get_business(business_id: int, db: Session = Depends(get_db)):
    service = BusinessService(db)
    return service.get_business(business_id)


@router.put("/{business_id}", response_model=BusinessResponse)
def update_business(business_id: int, business_in: BusinessUpdate, db: Session = Depends(get_db)):
    service = BusinessService(db)
    return service.update_business(business_id, business_in)


@router.delete("/{business_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_business(business_id: int, db: Session = Depends(get_db)):
    service = BusinessService(db)
    service.delete_business(business_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
