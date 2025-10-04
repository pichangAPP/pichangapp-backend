"""API routes for membership operations."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas import MembershipCreate, MembershipResponse, MembershipUpdate
from app.services import MembershipService

router = APIRouter(prefix="/memberships", tags=["memberships"])


@router.get("", response_model=list[MembershipResponse])
def list_memberships(db: Session = Depends(get_db)):
    service = MembershipService(db)
    return service.list_memberships()


@router.post("", response_model=MembershipResponse, status_code=status.HTTP_201_CREATED)
def create_membership(membership_in: MembershipCreate, db: Session = Depends(get_db)):
    service = MembershipService(db)
    return service.create_membership(membership_in)


@router.get("/{membership_id}", response_model=MembershipResponse)
def get_membership(membership_id: int, db: Session = Depends(get_db)):
    service = MembershipService(db)
    return service.get_membership(membership_id)


@router.put("/{membership_id}", response_model=MembershipResponse)
def update_membership(
    membership_id: int, membership_in: MembershipUpdate, db: Session = Depends(get_db)
):
    service = MembershipService(db)
    return service.update_membership(membership_id, membership_in)


@router.delete("/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_membership(membership_id: int, db: Session = Depends(get_db)):
    service = MembershipService(db)
    service.delete_membership(membership_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
