from typing import Optional

from sqlalchemy.orm import Session

from app.models.role import Role


def get_role_by_id(db: Session, role_id: int) -> Optional[Role]:
    return db.query(Role).filter(Role.id_role == role_id).first()
