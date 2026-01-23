"""Read-only access to auth schema data."""

from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.schemas.schedule import UserSummary


_USER_COLUMNS = """
    id_user,
    name,
    lastname,
    email,
    phone,
    imageurl,
    status
"""


def get_user_summary(db: Session, user_id: int) -> Optional[UserSummary]:
    query = text(
        f"""
        SELECT {_USER_COLUMNS}
        FROM auth.users
        WHERE id_user = :user_id
        """
    )
    row = db.execute(query, {"user_id": user_id}).mappings().first()
    if row is None:
        return None
    return UserSummary(**row)


def get_user_summaries(
    db: Session,
    user_ids: Iterable[int],
) -> dict[int, UserSummary]:
    unique_ids = {user_id for user_id in user_ids if user_id is not None}
    if not unique_ids:
        return {}

    query = text(
        f"""
        SELECT {_USER_COLUMNS}
        FROM auth.users
        WHERE id_user IN :user_ids
        """
    ).bindparams(bindparam("user_ids", expanding=True))

    rows = db.execute(query, {"user_ids": list(unique_ids)}).mappings().all()
    return {row["id_user"]: UserSummary(**row) for row in rows}


__all__ = ["get_user_summary", "get_user_summaries"]
