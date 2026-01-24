"""Read-only access to auth schema data."""

from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.schemas.manager import ManagerResponse


_MANAGER_COLUMNS = """
    id_user,
    name,
    lastname,
    email,
    phone,
    imageurl,
    birthdate,
    gender,
    city,
    district,
    status,
    id_role,
    created_at,
    updated_at
"""


def get_manager_summary(db: Session, manager_id: int) -> Optional[ManagerResponse]:
    query = text(
        f"""
        SELECT {_MANAGER_COLUMNS}
        FROM auth.users
        WHERE id_user = :manager_id
        """
    )
    row = db.execute(query, {"manager_id": manager_id}).mappings().first()
    if row is None:
        return None
    return ManagerResponse(**row)


def get_manager_summaries(
    db: Session,
    manager_ids: Iterable[int],
) -> dict[int, ManagerResponse]:
    unique_ids = {manager_id for manager_id in manager_ids if manager_id is not None}
    if not unique_ids:
        return {}

    query = text(
        f"""
        SELECT {_MANAGER_COLUMNS}
        FROM auth.users
        WHERE id_user IN :manager_ids
        """
    ).bindparams(bindparam("manager_ids", expanding=True))

    rows = db.execute(query, {"manager_ids": list(unique_ids)}).mappings().all()
    return {row["id_user"]: ManagerResponse(**row) for row in rows}


__all__ = ["get_manager_summary", "get_manager_summaries"]
