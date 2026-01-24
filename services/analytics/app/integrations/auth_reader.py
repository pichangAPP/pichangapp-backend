"""Read-only access to auth schema data."""

from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session


def get_user_summaries(
    db: Session,
    user_ids: Iterable[int],
) -> dict[int, dict[str, Optional[str]]]:
    unique_ids = {user_id for user_id in user_ids if user_id is not None}
    if not unique_ids:
        return {}

    query = text(
        """
        SELECT
            id_user,
            name,
            lastname,
            email,
            phone,
            imageurl,
            city,
            district
        FROM auth.users
        WHERE id_user IN :user_ids
        """
    ).bindparams(bindparam("user_ids", expanding=True))

    rows = db.execute(query, {"user_ids": list(unique_ids)}).mappings().all()
    return {row["id_user"]: dict(row) for row in rows}


__all__ = ["get_user_summaries"]
