"""Business logic for membership operations."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Membership
from app.repository import (
    create_membership as repo_create_membership,
    delete_membership as repo_delete_membership,
    get_membership as repo_get_membership,
    list_memberships as repo_list_memberships,
)
from app.schemas import MembershipCreate, MembershipUpdate


class MembershipService:
    """Service layer encapsulating membership operations."""

    def __init__(self, db: Session):
        self.db = db

    def list_memberships(self) -> list[Membership]:
        try:
            return repo_list_memberships(self.db)
        except SQLAlchemyError as exc:  # pragma: no cover - defensive
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to list memberships",
            ) from exc

    def get_membership(self, membership_id: int) -> Membership:
        membership = repo_get_membership(self.db, membership_id)
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Membership {membership_id} not found",
            )
        return membership

    def create_membership(self, membership_in: MembershipCreate) -> Membership:
        try:
            membership = Membership(**membership_in.model_dump())
            repo_create_membership(self.db, membership)
            self.db.commit()
            self.db.refresh(membership)
            return membership
        except SQLAlchemyError as exc:  # pragma: no cover - defensive
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create membership",
            ) from exc

    def update_membership(
        self, membership_id: int, membership_in: MembershipUpdate
    ) -> Membership:
        membership = self.get_membership(membership_id)
        update_data = membership_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(membership, field, value)
        try:
            self.db.flush()
            self.db.commit()
            self.db.refresh(membership)
            return membership
        except SQLAlchemyError as exc:  # pragma: no cover - defensive
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update membership",
            ) from exc

    def delete_membership(self, membership_id: int) -> None:
        membership = self.get_membership(membership_id)
        try:
            repo_delete_membership(self.db, membership)
            self.db.commit()
        except SQLAlchemyError as exc:  # pragma: no cover - defensive
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete membership",
            ) from exc
