"""Read-only access to payment schema data."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional, Sequence

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session


def get_payment_summaries(
    db: Session,
    payment_ids: Sequence[int],
) -> Dict[int, Dict[str, Any]]:
    """Return payment rows keyed by ``id_payment`` (empty if none or DB miss).

    Used by: RentHydrator to embed ``payment`` on ``RentResponse``.
    """
    unique = sorted({int(x) for x in payment_ids if x is not None})
    if not unique:
        return {}
    query = text(
        """
        SELECT id_payment, amount, currency, method, status, type, paid_at,
               transaction_id, reference
        FROM payment.payment
        WHERE id_payment IN :pids
        """
    ).bindparams(bindparam("pids", expanding=True))
    rows = db.execute(query, {"pids": unique}).mappings().all()
    out: Dict[int, Dict[str, Any]] = {}
    for row in rows:
        pid = int(row["id_payment"])
        out[pid] = {
            "id_payment": pid,
            "amount": row["amount"] if isinstance(row["amount"], Decimal) else Decimal(str(row["amount"])),
            "currency": row["currency"],
            "method": row["method"],
            "status": row["status"],
            "type": row["type"],
            "paid_at": row["paid_at"],
            "transaction_id": int(row["transaction_id"]),
            "reference": row["reference"],
        }
    return out


def get_payment_status(db: Session, payment_id: int) -> Optional[str]:
    query = text(
        """
        SELECT status
        FROM payment.payment
        WHERE id_payment = :payment_id
        """
    )
    return db.execute(query, {"payment_id": payment_id}).scalar_one_or_none()

def get_campus_digital_wallets(
    db: Session,
    *,
    campus_id: int,
) -> Optional[dict]:
    query = text(
        """
        SELECT
            uses_yape,
            yape_phone,
            yape_qr_url,
            uses_plin,
            plin_phone,
            plin_qr_url,
            status,
            created_at,
            updated_at
        FROM payment.payment_methods
        WHERE id_campus = :campus_id
        """
    )
    row = db.execute(query, {"campus_id": campus_id}).mappings().first()
    if row is None:
        return None

    return {
        "yape_phone": row["yape_phone"] if row["uses_yape"] else None,
        "yape_qr_url": row["yape_qr_url"] if row["uses_yape"] else None,
        "plin_phone": row["plin_phone"] if row["uses_plin"] else None,
        "plin_qr_url": row["plin_qr_url"] if row["uses_plin"] else None,
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }

__all__ = ["get_campus_digital_wallets", "get_payment_status", "get_payment_summaries"]
