from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.session import UserSession


def create_session(db: Session, session: UserSession) -> UserSession:
    db.add(session)
    db.flush()
    return session

def delete_sessions_by_user(
    db: Session, user_id: int, exclude_session_id: Optional[int] = None
) -> None:
    query = db.query(UserSession).filter(UserSession.id_user == user_id)
    if exclude_session_id is not None:
        query = query.filter(UserSession.id_session != exclude_session_id)

    query.delete(synchronize_session=False)
    db.flush()

def get_active_sessions(db: Session, user_id: int) -> List[UserSession]:
    return (
        db.query(UserSession)
        .filter(UserSession.id_user == user_id, UserSession.is_active.is_(True))
        .all()
    )


def deactivate_session(db: Session, session_id: int) -> Optional[UserSession]:
    session = db.query(UserSession).filter(UserSession.id_session == session_id).first()
    if session:
        session.is_active = False
        db.flush()
    return session
