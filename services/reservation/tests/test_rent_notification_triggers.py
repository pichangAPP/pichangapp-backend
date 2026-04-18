"""Unit tests for rent → Kafka notification rules (no DB).

PUT **admin** vs PUT **usuario** tienen funciones distintas en ``notification_triggers``.
"""
from __future__ import annotations

import pytest

from app.domain.rent.notification_triggers import (
    notification_event_types_after_rent_create,
    notification_event_types_after_rent_update_admin,
    notification_event_types_after_rent_update_user,
)


class TestNotificationEventTypesAfterRentUpdateAdmin:
    """``PUT …/rents/admin/{id}`` → ``notification_event_types_after_rent_update_admin``."""

    @pytest.mark.parametrize(
        ("orig", "new", "had_before", "has_after", "expected"),
        [
            ("pending_payment", "under_review", False, False, []),
            ("under_review", "reserved", False, False, []),
            ("pending_payment", "reserved", False, False, []),
            ("pending_payment", "rejected_not_received", False, False, []),
            (
                "pending_payment",
                "pending_payment",
                False,
                True,
                ["rent.booking_notice"],
            ),
            (
                "reserved",
                "reserved",
                False,
                True,
                ["rent.booking_notice"],
            ),
            ("under_review", "under_review", True, True, []),
            ("reserved", "reserved", True, True, []),
            ("pending_payment", "pending_payment", True, True, []),
            ("pending_payment", "under_review", True, True, ["rent.booking_notice"]),
            ("pending_payment", "under_review", False, True, ["rent.booking_notice"]),
            ("under_review", "reserved", True, True, ["rent.approved"]),
            (
                "under_review",
                "rejected_not_received",
                True,
                True,
                ["rent.rejected"],
            ),
            ("reserved", "cancelled", True, True, ["rent.verdict"]),
            ("reserved", "fullfilled", True, True, ["rent.verdict"]),
            ("under_review", "pending_payment", True, True, ["rent.booking_notice"]),
        ],
    )
    def test_admin_update_matrix(
        self,
        orig: str,
        new: str,
        had_before: bool,
        has_after: bool,
        expected: list[str],
    ) -> None:
        assert (
            notification_event_types_after_rent_update_admin(
                original_status=orig,
                updated_status=new,
                rent_had_id_payment_before=had_before,
                rent_has_id_payment_after=has_after,
            )
            == expected
        )


class TestNotificationEventTypesAfterRentUpdateUser:
    """``PUT …/rents/{id}`` → ``notification_event_types_after_rent_update_user``."""

    @pytest.mark.parametrize(
        ("notify", "orig", "new", "has_after", "expected"),
        [
            # Solo vinculación/cambio de id_payment, mismo estado
            (True, "pending_payment", "pending_payment", True, ["rent.payment_received"]),
            # Solo cambio de estado con id_payment (sin notify flag)
            (
                False,
                "pending_payment",
                "under_review",
                True,
                ["rent.booking_notice"],
            ),
            (
                False,
                "under_review",
                "reserved",
                True,
                ["rent.approved"],
            ),
            # Pago nuevo + transición de estado (típico envío comprobante)
            (
                True,
                "pending_payment",
                "under_review",
                True,
                ["rent.payment_received", "rent.booking_notice"],
            ),
            # Sin id_payment al final: no eventos de estado aunque cambie status
            (False, "pending_payment", "under_review", False, []),
            # Mismo estado, sin cambio de id_payment en body
            (False, "under_review", "under_review", True, []),
        ],
    )
    def test_user_update_matrix(
        self,
        notify: bool,
        orig: str,
        new: str,
        has_after: bool,
        expected: list[str],
    ) -> None:
        assert (
            notification_event_types_after_rent_update_user(
                original_status=orig,
                updated_status=new,
                notify_after_payment=notify,
                rent_has_id_payment_after=has_after,
            )
            == expected
        )


class TestNotificationEventTypesAfterRentCreate:
    """POST create (compartido user/admin/combo)."""

    def test_pending_payment_without_payment_notifies(self) -> None:
        assert notification_event_types_after_rent_create(
            status="pending_payment",
            rent_has_id_payment=False,
        ) == ["rent.booking_notice"]

    def test_under_review_without_payment_notifies(self) -> None:
        assert notification_event_types_after_rent_create(
            status="under_review",
            rent_has_id_payment=False,
        ) == ["rent.booking_notice"]

    def test_reserved_without_payment_silent(self) -> None:
        assert notification_event_types_after_rent_create(
            status="reserved",
            rent_has_id_payment=False,
        ) == []

    def test_reserved_with_payment_approved(self) -> None:
        assert notification_event_types_after_rent_create(
            status="reserved",
            rent_has_id_payment=True,
        ) == ["rent.approved"]

    def test_rejected_with_payment(self) -> None:
        assert notification_event_types_after_rent_create(
            status="rejected_invalid_proof",
            rent_has_id_payment=True,
        ) == ["rent.rejected"]

    def test_rejected_without_payment_silent(self) -> None:
        assert notification_event_types_after_rent_create(
            status="rejected_invalid_proof",
            rent_has_id_payment=False,
        ) == []

    def test_cancelled_with_payment_verdict(self) -> None:
        assert notification_event_types_after_rent_create(
            status="cancelled",
            rent_has_id_payment=True,
        ) == ["rent.verdict"]

    def test_cancelled_without_payment_silent(self) -> None:
        assert notification_event_types_after_rent_create(
            status="cancelled",
            rent_has_id_payment=False,
        ) == []
