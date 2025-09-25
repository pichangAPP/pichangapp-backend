from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.user import User


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, user: User) -> User:
    db.add(user)
    db.flush()
    return user


def get_all_users(db: Session) -> List[User]:
    return db.query(User).all()


def get_users_by_status(db: Session, status: str) -> List[User]:
    return db.query(User).filter(User.status == status).all()


def get_users_by_role(db: Session, role_id: int) -> List[User]:
    return db.query(User).filter(User.id_role == role_id).all()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id_user == user_id).first()
