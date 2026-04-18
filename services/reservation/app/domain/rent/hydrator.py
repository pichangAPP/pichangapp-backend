"""Mapping helpers that hydrate rent models into API responses."""
from __future__ import annotations

from datetime import date, datetime, time
from itertools import groupby
from typing import List, Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.error_codes import (
    FIELD_NOT_FOUND,
    RENT_NOT_FOUND,
    SCHEDULE_NOT_FOUND,
    http_error,
)
from app.integrations import auth_reader, booking_reader, payment_reader
from app.models.rent import Rent
from app.models.schedule import Schedule
from app.repository import schedule_repository
from app.schemas.rent import RentPaymentSummary, RentResponse, ScheduleSummary
from app.schemas.schedule import FieldSummary, UserSummary


def _campus_view_row_sort_key(row: dict) -> tuple:
    """Order campus view rows: newest ``date_create`` first, then rent id, primary, schedule."""
    dc = row.get("date_create")
    if isinstance(dc, datetime):
        neg_ts = -dc.timestamp()
    elif isinstance(dc, date):
        neg_ts = -datetime.combine(dc, time.min).timestamp()
    else:
        neg_ts = float("inf")
    return (
        neg_ts,
        int(row["id_rent"]),
        not bool(row.get("rent_schedule_is_primary", True)),
        int(row["id_schedule"]),
    )


def ordered_schedules_for_rent(db: Session, rent: Rent) -> List[Schedule]:
    """Return schedules for a rent (combined first), ordered for display."""
    if rent.schedule_links:
        links = sorted(
            rent.schedule_links,
            key=lambda x: (not x.is_primary, x.id_schedule),
        )
        out = [ln.schedule for ln in links if ln.schedule is not None]
        if out:
            return out
    if rent.schedule is not None:
        return [rent.schedule]
    if rent.id_schedule is not None:
        sch = schedule_repository.get_schedule(db, rent.id_schedule)
        if sch is not None:
            return [sch]
    return []


class RentHydrator:
    """Build rent responses enriched with schedule, field, and user data."""

    def __init__(self, db: Session) -> None:
        """Initialize with a DB session for lookups.

        Used by: RentService responses.
        """
        self.db = db

    def hydrate_rent(self, rent: Optional[Rent]) -> RentResponse:
        """Hydrate a single rent into its API response shape.

        Used by: RentService get/create/update flows.
        """
        if rent is None:
            raise http_error(
                RENT_NOT_FOUND,
                detail="Rent not found",
            )
        return self.hydrate_rents([rent])[0]

    def hydrate_rents(self, rents: Sequence[Rent]) -> List[RentResponse]:
        """Hydrate a list of rents into API response shapes.

        Used by: RentService list endpoints.
        """
        all_schedules: List[Schedule] = []
        for rent in rents:
            all_schedules.extend(ordered_schedules_for_rent(self.db, rent))

        field_ids = [s.id_field for s in all_schedules if s.id_field]
        user_ids = [s.id_user for s in all_schedules if s.id_user]

        fields = booking_reader.get_field_summaries(self.db, field_ids)
        try:
            users = auth_reader.get_user_summaries(self.db, user_ids)
        except auth_reader.AuthReaderError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

        payment_ids = [int(r.id_payment) for r in rents if r.id_payment is not None]
        payments_raw = payment_reader.get_payment_summaries(self.db, payment_ids)

        responses: List[RentResponse] = []
        for rent in rents:
            ordered = ordered_schedules_for_rent(self.db, rent)
            if not ordered:
                raise http_error(
                    SCHEDULE_NOT_FOUND,
                    detail="Associated schedule not found",
                )
            summaries: List[ScheduleSummary] = []
            for schedule in ordered:
                field = fields.get(schedule.id_field)
                user = users.get(schedule.id_user)
                summaries.append(
                    self._build_schedule_summary(
                        schedule,
                        field=field,
                        user=user,
                    )
                )
            pay: Optional[RentPaymentSummary] = None
            if rent.id_payment is not None:
                row = payments_raw.get(int(rent.id_payment))
                if row is not None:
                    pay = RentPaymentSummary(**row)
            responses.append(self._build_rent_response(rent, summaries, pay))
        return responses

    def build_rent_responses_from_rows(self, rows: Sequence[dict]) -> List[RentResponse]:
        """Build rent responses from denormalized query rows.

        Used by: RentService list_rents_by_campus view.
        """
        if not rows:
            return []

        sorted_rows = sorted(rows, key=_campus_view_row_sort_key)
        pay_ids = [int(r["id_payment"]) for r in sorted_rows if r.get("id_payment")]
        payments_raw = payment_reader.get_payment_summaries(self.db, pay_ids)
        responses: List[RentResponse] = []
        for _rent_id, group in groupby(sorted_rows, key=lambda r: r["id_rent"]):
            grp = list(group)
            schedule_summaries: List[ScheduleSummary] = []
            for row in grp:
                field = FieldSummary(
                    id_field=row["field_id_field"],
                    field_name=row["field_name"],
                    capacity=row["field_capacity"],
                    surface=row["field_surface"],
                    measurement=row["field_measurement"],
                    price_per_hour=row["field_price_per_hour"],
                    status=row["field_status"],
                    open_time=row["field_open_time"],
                    close_time=row["field_close_time"],
                    minutes_wait=row["field_minutes_wait"],
                    id_sport=row["field_id_sport"],
                    id_campus=row["field_id_campus"],
                )
                user = None
                if row["user_id_user"] is not None:
                    user = UserSummary(
                        id_user=row["user_id_user"],
                        name=row["user_name"],
                        lastname=row["user_lastname"],
                        email=row["user_email"],
                        phone=row["user_phone"],
                        imageurl=row["user_imageurl"],
                        status=row["user_status"],
                    )
                schedule_summaries.append(
                    ScheduleSummary(
                        id_schedule=row["id_schedule"],
                        day_of_week=row["schedule_day_of_week"],
                        start_time=row["schedule_start_time"],
                        end_time=row["schedule_end_time"],
                        status=row["schedule_status"],
                        id_status=row.get("schedule_id_status"),
                        price=row["schedule_price"],
                        field=field,
                        user=user,
                    )
                )
            first = grp[0]
            primary = schedule_summaries[0]
            pay: Optional[RentPaymentSummary] = None
            if first.get("id_payment") is not None:
                prow = payments_raw.get(int(first["id_payment"]))
                if prow is not None:
                    pay = RentPaymentSummary(**prow)
            responses.append(
                RentResponse(
                    id_rent=first["id_rent"],
                    period=first["period"],
                    start_time=first["start_time"],
                    end_time=first["end_time"],
                    initialized=first["initialized"],
                    finished=first["finished"],
                    status=first["status"],
                    id_status=first.get("rent_id_status"),
                    minutes=first["minutes"],
                    mount=first["mount"],
                    date_log=first["date_log"],
                    date_create=first["date_create"],
                    payment_deadline=first["payment_deadline"],
                    capacity=first["capacity"],
                    id_payment=first["id_payment"],
                    payment_code=first.get("payment_code"),
                    payment_proof_url=first.get("payment_proof_url"),
                    payment_reviewed_at=first.get("payment_reviewed_at"),
                    payment_reviewed_by=first.get("payment_reviewed_by"),
                    customer_full_name=first.get("customer_full_name"),
                    customer_phone=first.get("customer_phone"),
                    customer_email=first.get("customer_email"),
                    customer_document=first.get("customer_document"),
                    customer_notes=first.get("customer_notes"),
                    id_schedule=primary.id_schedule,
                    schedules=schedule_summaries,
                    payment=pay,
                )
            )
        return responses

    @staticmethod
    def _build_schedule_summary(
        schedule: Schedule,
        *,
        field: Optional[FieldSummary],
        user: Optional[UserSummary],
    ) -> ScheduleSummary:
        """Build the nested schedule summary for a rent response.

        Used by: hydrate_rents.
        """
        if field is None:
            raise http_error(
                FIELD_NOT_FOUND,
                detail="Associated field not found",
            )
        return ScheduleSummary(
            id_schedule=schedule.id_schedule,
            day_of_week=schedule.day_of_week,
            start_time=schedule.start_time,
            end_time=schedule.end_time,
            status=schedule.status,
            id_status=schedule.id_status,
            price=schedule.price,
            field=field,
            user=user,
        )

    @staticmethod
    def _build_rent_response(
        rent: Rent,
        schedule_summaries: List[ScheduleSummary],
        payment: Optional[RentPaymentSummary],
    ) -> RentResponse:
        """Build the final RentResponse object.

        Used by: hydrate_rents/build_rent_responses_from_rows.
        """
        primary = schedule_summaries[0]
        return RentResponse(
            id_rent=rent.id_rent,
            period=rent.period,
            start_time=rent.start_time,
            end_time=rent.end_time,
            initialized=rent.initialized,
            finished=rent.finished,
            status=rent.status,
            id_status=rent.id_status,
            minutes=rent.minutes,
            mount=rent.mount,
            date_log=rent.date_log,
            date_create=rent.date_create,
            payment_deadline=rent.payment_deadline,
            capacity=rent.capacity,
            id_payment=rent.id_payment,
            payment_code=rent.payment_code,
            payment_proof_url=rent.payment_proof_url,
            payment_reviewed_at=rent.payment_reviewed_at,
            payment_reviewed_by=rent.payment_reviewed_by,
            customer_full_name=rent.customer_full_name,
            customer_phone=rent.customer_phone,
            customer_email=rent.customer_email,
            customer_document=rent.customer_document,
            customer_notes=rent.customer_notes,
            id_schedule=primary.id_schedule,
            schedules=schedule_summaries,
            payment=payment,
        )


__all__ = ["RentHydrator", "ordered_schedules_for_rent"]
