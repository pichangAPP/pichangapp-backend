"""Pure rules for when reservation publishes rent notification events to Kafka.

Rent status (``rent.status``) is separate from payment lifecycle on the **payment**
service (``payment`` row state, amount, etc.). Only rent endpoints evaluate these
rules; updating a payment record without touching the rent does not run this module.

``PUT`` **usuario** vs ``PUT`` **admin** usan reglas distintas (ver funciones
``*_user`` y ``*_admin``).
"""

from __future__ import annotations

from typing import List

from app.core.status_constants import (
    RENT_BOOKING_NOTICE_STATUS_CODES,
    RENT_RESERVED_STATUS_CODE,
)


def notification_event_types_after_rent_update_admin(
    *,
    original_status: str,
    updated_status: str,
    rent_had_id_payment_before: bool,
    rent_has_id_payment_after: bool,
) -> List[str]:
    """Kafka event types after ``PUT …/rents/admin/{id}``.

    The persisted rent must end with ``id_payment`` set (``rent_has_id_payment_after``).
    If not, nothing is emitted.

    **A — Cambio de estado de la renta** (normalizado antes/después). Con
    ``id_payment`` presente al final:

    - ``reserved`` → ``rent.approved``
    - ``rejected_*`` → ``rent.rejected``
    - estados en ``RENT_BOOKING_NOTICE_STATUS_CODES`` → ``rent.booking_notice``
    - otro → ``rent.verdict``

    **B — Primera vinculación de ``id_payment``** en la renta sin cambiar
    ``rent.status`` → ``rent.booking_notice``.

    Sustituir un ``id_payment`` por otro cuando la renta ya tenía uno, sin cambio de
    estado, no emite.
    """
    if not rent_has_id_payment_after:
        return []
    orig = (original_status or "").strip().lower()
    new = (updated_status or "").strip().lower()
    status_changed = new != orig
    id_payment_newly_linked = rent_has_id_payment_after and not rent_had_id_payment_before

    if status_changed:
        if new == RENT_RESERVED_STATUS_CODE:
            return ["rent.approved"]
        if new.startswith("rejected_"):
            return ["rent.rejected"]
        if new in RENT_BOOKING_NOTICE_STATUS_CODES:
            return ["rent.booking_notice"]
        return ["rent.verdict"]

    if id_payment_newly_linked:
        return ["rent.booking_notice"]

    return []


def notification_event_types_after_rent_update_user(
    *,
    original_status: str,
    updated_status: str,
    notify_after_payment: bool,
    rent_has_id_payment_after: bool,
) -> List[str]:
    """Kafka event types after ``PUT …/rents/{id}`` (flujo jugador / no admin).

    - ``rent.payment_received`` cuando en el body se asigna o **cambia** el
      ``id_payment`` de la renta respecto al valor previo (``notify_after_payment``).
    - Además, si tras el PUT la renta tiene ``id_payment`` y **cambió**
      ``rent.status``, se añade el evento según el nuevo estado (misma tabla que
      admin: approved / rejected / booking_notice / verdict).

    No se usa la regla admin de "solo primera vinculación con booking_notice": el
    disparo clásico de pago es ``rent.payment_received``.
    """
    events: List[str] = []
    if notify_after_payment:
        events.append("rent.payment_received")
    if not rent_has_id_payment_after:
        return events
    orig = (original_status or "").strip().lower()
    new = (updated_status or "").strip().lower()
    if new == orig:
        return events
    if new == RENT_RESERVED_STATUS_CODE:
        events.append("rent.approved")
    elif new.startswith("rejected_"):
        events.append("rent.rejected")
    elif new in RENT_BOOKING_NOTICE_STATUS_CODES:
        events.append("rent.booking_notice")
    else:
        events.append("rent.verdict")
    return events


def notification_event_types_after_rent_create(
    *,
    status: str,
    rent_has_id_payment: bool,
) -> List[str]:
    """Kafka event types after ``POST`` create rent (user, admin, or combo).

    On **create**, a first notice for ``pending_payment`` (and other
    ``RENT_BOOKING_NOTICE_STATUS_CODES``) is allowed **without** ``id_payment``,
    e.g. admin modal "aún no cobró". ``reserved`` / ``rejected_*`` still require a
    linked ``id_payment`` for ``rent.approved`` / ``rent.rejected``. Other statuses
    with ``id_payment`` set emit ``rent.verdict``.
    """
    st = (status or "").strip().lower()
    if st == RENT_RESERVED_STATUS_CODE and rent_has_id_payment:
        return ["rent.approved"]
    if st.startswith("rejected_") and rent_has_id_payment:
        return ["rent.rejected"]
    if st in RENT_BOOKING_NOTICE_STATUS_CODES:
        return ["rent.booking_notice"]
    if rent_has_id_payment:
        return ["rent.verdict"]
    return []


__all__ = [
    "notification_event_types_after_rent_create",
    "notification_event_types_after_rent_update_admin",
    "notification_event_types_after_rent_update_user",
]
