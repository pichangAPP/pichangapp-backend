from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas import CampusCreate, CampusResponse, CampusUpdate
from app.services import CampusService

router = APIRouter(tags=["campuses"])


@router.get("/businesses/{business_id}/campuses", response_model=list[CampusResponse])
def list_campuses(business_id: int, db: Session = Depends(get_db)):
    service = CampusService(db)
    return service.list_campuses(business_id)


@router.post(
    "/businesses/{business_id}/campuses",
    response_model=CampusResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_campus(business_id: int, campus_in: CampusCreate, db: Session = Depends(get_db)):
    service = CampusService(db)
    return service.create_campus(business_id, campus_in)


@router.get("/campuses/{campus_id}", response_model=CampusResponse)
def get_campus(campus_id: int, db: Session = Depends(get_db)):
    service = CampusService(db)
    return service.get_campus(campus_id)


@router.put("/campuses/{campus_id}", response_model=CampusResponse)
def update_campus(campus_id: int, campus_in: CampusUpdate, db: Session = Depends(get_db)):
    service = CampusService(db)
    return service.update_campus(campus_id, campus_in)


@router.delete("/campuses/{campus_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campus(campus_id: int, db: Session = Depends(get_db)):
    service = CampusService(db)
    service.delete_campus(campus_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
