"""Rent service orchestrating rent workflows."""
from __future__ import annotations

from typing import List, Optional

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Session

from app.core.error_codes import RENT_NOT_FOUND, SCHEDULE_NOT_FOUND, http_error
from app.core.status_constants import (
    RENT_FINAL_STATUS_CODES,
    RENT_HOLD_STATUS_CODES,
    RENT_PENDING_PAYMENT_STATUS_CODE,
    RENT_RESERVED_STATUS_CODE,
    RENT_UNDER_REVIEW_STATUS_CODE,
    SCHEDULE_AVAILABLE_STATUS_CODE,
    SCHEDULE_EXCLUDED_CONFLICT_STATUS_CODES,
    SCHEDULE_HOLD_PAYMENT_STATUS_CODE,
    SCHEDULE_PENDING_STATUS_CODE,
    SCHEDULE_RESERVED_STATUS_CODE,
)
from app.integrations import booking_reader
from app.models.rent import Rent
from app.models.schedule import Schedule
from app.repository import rent_repository, schedule_repository
from app.schemas.rent import (
    RentAdminCreate,
    RentAdminUpdate,
    RentCancelRequest,
    RentCancelResponse,
    RentCreate,
    RentCreateCombo,
    RentPaymentResponse,
    RentResponse,
    RentUpdate,
)
from app.domain.rent.combo import (
    compute_combo_mount,
    compute_combo_mount_from_price_per_hour,
    validate_combo_schedules,
)
from app.domain.rent.defaults import (
    apply_admin_note,
    apply_schedule_defaults,
    compute_payment_deadline_from_schedule,
    ensure_admin_customer_fields,
)
from app.domain.rent.hydrator import ordered_schedules_for_rent
from app.domain.rent.field_status import (
    refresh_field_status,
    reset_field_status_after_time,
)
from app.domain.rent.hydrator import RentHydrator
from app.domain.rent.notification_triggers import (
    notification_event_types_after_rent_create,
    notification_event_types_after_rent_update_admin,
    notification_event_types_after_rent_update_user,
)
from app.domain.rent.notifications import RentNotificationPublisher
from app.domain.rent.payments import (
    build_payment_instructions,
    generate_payment_code,
    validate_payment,
)
from app.domain.rent.validations import (
    ensure_field_exists,
    ensure_schedule_available,
    ensure_schedule_not_started,
    ensure_user_exists,
    get_schedule,
)
from app.domain.schedule.validations import ensure_field_not_reserved
from app.domain.schedule.weekly_closure import raise_if_schedule_blocked_by_weekly_closure
from app.domain.status_resolver import resolve_status_id, resolve_status_pair

class RentService:
    """Coordinates rent CRUD, validation, and notification workflows."""

    _EXCLUDED_RENT_STATUSES = RENT_FINAL_STATUS_CODES

    def __init__(self, db: Session) -> None:
        self.db = db

    @classmethod
    def _active_excluded_statuses(cls) -> List[str]:
        return [value for value in cls._EXCLUDED_RENT_STATUSES if value]

    def _field_ids_for_rent(self, rent: Rent) -> List[int]:
        out: List[int] = []
        for sch in ordered_schedules_for_rent(self.db, rent):
            if sch.id_field is not None:
                out.append(int(sch.id_field))
        return list(dict.fromkeys(out))

    def _schedule_link_count(self, rent: Rent) -> int:
        if rent.schedule_links:
            return len(rent.schedule_links)
        return 1 if rent.id_schedule is not None else 0

    def _primary_schedule_id(self, rent: Rent) -> Optional[int]:
        if rent.id_schedule is not None:
            return int(rent.id_schedule)
        for ln in rent.schedule_links or []:
            if ln.is_primary:
                return int(ln.id_schedule)
        if rent.schedule_links:
            return int(rent.schedule_links[0].id_schedule)
        return None

    def _schedules_for_admin_transition(
        self,
        *,
        rent: Rent,
        original_schedules: List[Schedule],
        target_schedule: Schedule,
        schedule_changed: bool,
    ) -> List[Schedule]:
        """Return schedules affected by an admin status transition."""
        if schedule_changed and self._schedule_link_count(rent) <= 1:
            return [target_schedule]
        if original_schedules:
            return original_schedules
        return [target_schedule]

    def _ensure_schedules_reusable_for_reservation(
        self,
        *,
        rent: Rent,
        schedules: List[Schedule],
    ) -> None:
        """Ensure schedules can be reused before setting a rent to reserved."""
        for schedule in schedules:
            status_value = (schedule.status or "").strip().lower()
            if status_value != SCHEDULE_AVAILABLE_STATUS_CODE:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Schedule {schedule.id_schedule} is not available. "
                        "Only available schedules can be reserved by admin."
                    ),
                )
            ensure_schedule_available(
                self.db,
                schedule.id_schedule,
                excluded_statuses=self._active_excluded_statuses(),
                exclude_rent_id=rent.id_rent,
            )
            raise_if_schedule_blocked_by_weekly_closure(self.db, schedule)
            self._ensure_field_window_clear_for_new_rent(
                schedule,
                exclude_schedule_id=schedule.id_schedule,
                exclude_rent_id=rent.id_rent,
            )

    def _set_schedules_status(
        self,
        *,
        schedules: List[Schedule],
        status_code: str,
    ) -> None:
        """Persist the same status on all provided schedules."""
        status_id = resolve_status_id(
            self.db,
            entity="schedule",
            code=status_code,
        )
        for schedule in schedules:
            if (schedule.status or "").strip().lower() == status_code:
                continue
            schedule.status = status_code
            schedule.id_status = status_id
            schedule_repository.save_schedule(self.db, schedule)

    def _get_rent_model(self, rent_id: int) -> Rent:
        rent = rent_repository.get_rent(self.db, rent_id)
        if rent is None:
            raise http_error(
                RENT_NOT_FOUND,
                detail="Rent not found",
            )
        return rent

    def _ensure_field_window_clear_for_new_rent(
        self,
        schedule: Schedule,
        *,
        exclude_schedule_id: int,
        exclude_rent_id: Optional[int] = None,
    ) -> None:
        """Block double booking on the same field and overlapping window.

        Uses the same schedule-status exclusions as ``POST /schedules`` (e.g.
        ``available`` does not block). Always blocks overlapping **active** rents
        (``under_review``, ``pending_payment``, etc.) via ``field_has_active_rent_in_range``.
        """
        if schedule.id_field is None:
            return
        ensure_field_not_reserved(
            self.db,
            field_id=int(schedule.id_field),
            start_time=schedule.start_time,
            end_time=schedule.end_time,
            exclude_schedule_id=exclude_schedule_id,
            excluded_schedule_statuses=SCHEDULE_EXCLUDED_CONFLICT_STATUS_CODES,
            excluded_rent_statuses=self._active_excluded_statuses(),
            exclude_rent_id=exclude_rent_id,
        )

    def _emit_rent_update_notifications(
        self,
        *,
        updated_rent: Optional[Rent],
        original_status: str,
        rent_had_id_payment_before: bool,
        notify_after_payment: bool,
        is_admin_rent: bool,
        background_tasks: Optional[BackgroundTasks],
    ) -> None:
        """Publish Kafka notification events after a rent PUT.

        Admin and user flows use different pure rules in ``notification_triggers``.
        """
        if updated_rent is None:
            return
        if is_admin_rent:
            event_types = notification_event_types_after_rent_update_admin(
                original_status=original_status,
                updated_status=updated_rent.status or "",
                rent_had_id_payment_before=rent_had_id_payment_before,
                rent_has_id_payment_after=updated_rent.id_payment is not None,
            )
        else:
            event_types = notification_event_types_after_rent_update_user(
                original_status=original_status,
                updated_status=updated_rent.status or "",
                notify_after_payment=notify_after_payment,
                rent_has_id_payment_after=updated_rent.id_payment is not None,
            )
        if not event_types:
            return

        if background_tasks is not None:
            if len(event_types) == 1:
                background_tasks.add_task(
                    RentNotificationPublisher.publish_by_id,
                    rent_id=updated_rent.id_rent,
                    event_type=event_types[0],
                )
            else:
                background_tasks.add_task(
                    RentNotificationPublisher.publish_events_by_id,
                    rent_id=updated_rent.id_rent,
                    event_types=event_types,
                )
        else:
            publisher = RentNotificationPublisher(self.db)
            for event_type in event_types:
                publisher.publish(
                    rent=updated_rent,
                    event_type=event_type,
                )

    def _emit_rent_create_notifications(
        self,
        rent: Optional[Rent],
        *,
        background_tasks: Optional[BackgroundTasks],
    ) -> None:
        """Publish Kafka events after POST create (first persisted rent state)."""
        if rent is None:
            return
        event_types = notification_event_types_after_rent_create(
            status=rent.status or "",
            rent_has_id_payment=rent.id_payment is not None,
        )
        if not event_types:
            return

        if background_tasks is not None:
            if len(event_types) == 1:
                background_tasks.add_task(
                    RentNotificationPublisher.publish_by_id,
                    rent_id=rent.id_rent,
                    event_type=event_types[0],
                )
            else:
                background_tasks.add_task(
                    RentNotificationPublisher.publish_events_by_id,
                    rent_id=rent.id_rent,
                    event_types=event_types,
                )
        else:
            publisher = RentNotificationPublisher(self.db)
            for event_type in event_types:
                publisher.publish(
                    rent=rent,
                    event_type=event_type,
                )

    def list_rents(
        self,
        *,
        status_filter: Optional[str] = None,
        exclude_status: Optional[str] = None,
        schedule_id: Optional[int] = None,
    ) -> List[RentResponse]:
        hydrator = RentHydrator(self.db)
        rents = rent_repository.list_rents(
            self.db,
            status_filter=status_filter,
            exclude_status=exclude_status,
            schedule_id=schedule_id,
            order_by_created=True,
            sort_desc=True,
        )
        return hydrator.hydrate_rents(rents)

    def list_rents_by_campus(
        self,
        campus_id: int,
        *,
        status_filter: Optional[str] = None,
        exclude_status: Optional[str] = None,
    ) -> List[RentResponse]:
        hydrator = RentHydrator(self.db)
        rows = rent_repository.list_rents_by_campus_view(
            self.db,
            campus_id=campus_id,
            status_filter=status_filter,
            exclude_status=exclude_status,
        )
        return hydrator.build_rent_responses_from_rows(rows)

    def list_rents_by_field(
        self,
        field_id: int,
        *,
        status_filter: Optional[str] = None,
        exclude_status: Optional[str] = None,
    ) -> List[RentResponse]:
        hydrator = RentHydrator(self.db)
        ensure_field_exists(self.db, field_id)
        rents = rent_repository.list_rents(
            self.db,
            status_filter=status_filter,
            exclude_status=exclude_status,
            field_id=field_id,
        )
        return hydrator.hydrate_rents(rents)

    def list_rents_by_user(
        self,
        user_id: int,
        *,
        status_filter: Optional[str] = None,
        exclude_status: Optional[str] = None,
    ) -> List[RentResponse]:
        hydrator = RentHydrator(self.db)
        ensure_user_exists(self.db, user_id)
        rents = rent_repository.list_rents(
            self.db,
            status_filter=status_filter,
            exclude_status=exclude_status,
            user_id=user_id,
        )
        return hydrator.hydrate_rents(rents)

    def list_user_rent_history(
        self,
        user_id: int,
        *,
        status_filter: Optional[str] = None,
        exclude_status: Optional[str] = None,
    ) -> List[RentResponse]:
        hydrator = RentHydrator(self.db)
        ensure_user_exists(self.db, user_id)
        rents = rent_repository.list_rents(
            self.db,
            status_filter=status_filter,
            exclude_status=exclude_status,
            user_id=user_id,
            sort_desc=True,
        )
        return hydrator.hydrate_rents(rents)

    def get_rent(self, rent_id: int) -> RentResponse:
        hydrator = RentHydrator(self.db)
        rent = self._get_rent_model(rent_id)
        return hydrator.hydrate_rent(rent)

    def create_rent(
        self,
        payload: RentCreate,
        *,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> RentPaymentResponse:
        hydrator = RentHydrator(self.db)
        if payload.status != RENT_PENDING_PAYMENT_STATUS_CODE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Create rent only supports status 'pending_payment'",
            )

        schedule = get_schedule(self.db, payload.id_schedule)
        ensure_schedule_not_started(schedule)
        ensure_schedule_available(
            self.db,
            schedule.id_schedule,
            excluded_statuses=self._active_excluded_statuses(),
        )
        raise_if_schedule_blocked_by_weekly_closure(self.db, schedule)
        self._ensure_field_window_clear_for_new_rent(
            schedule,
            exclude_schedule_id=schedule.id_schedule,
        )
        field_summary = (
            booking_reader.get_field_summary(self.db, schedule.id_field)
            if schedule.id_field is not None
            else None
        )

        rent_data = payload.model_dump(exclude_unset=True)
        status_code, status_id = resolve_status_pair(
            self.db,
            entity="rent",
            status_code=RENT_PENDING_PAYMENT_STATUS_CODE,
            status_id=rent_data.get("id_status"),
        )
        rent_data["status"] = status_code
        rent_data["id_status"] = status_id
        if not rent_data.get("payment_code"):
            rent_data["payment_code"] = generate_payment_code()
        rent_data.pop("start_time", None)
        rent_data.pop("end_time", None)

        rent_data.setdefault(
            "payment_deadline",
            compute_payment_deadline_from_schedule(schedule),
        )

        apply_schedule_defaults(
            self.db,
            schedule=schedule,
            rent_data=rent_data,
            schedule_changed=True,
            field_summary=field_summary,
        )

        if rent_data.get("id_payment") is not None:
            validate_payment(self.db, int(rent_data["id_payment"]))

        rent = rent_repository.create_rent(self.db, rent_data)
        rent_repository.add_rent_schedule_link(
            self.db,
            rent_id=rent.id_rent,
            schedule_id=schedule.id_schedule,
            is_primary=True,
        )
        schedule.status = SCHEDULE_HOLD_PAYMENT_STATUS_CODE
        schedule.id_status = resolve_status_id(
            self.db,
            entity="schedule",
            code=SCHEDULE_HOLD_PAYMENT_STATUS_CODE,
        )
        schedule_repository.save_schedule(self.db, schedule)

        refresh_field_status(
            self.db,
            schedule.id_field,
            excluded_statuses=self._active_excluded_statuses(),
        )

        if background_tasks is not None:
            background_tasks.add_task(
                reset_field_status_after_time,
                field_id=schedule.id_field,
                end_time=rent.end_time,
                excluded_statuses=self._active_excluded_statuses(),
            )

        persisted = rent_repository.get_rent(self.db, rent.id_rent)
        self._emit_rent_create_notifications(
            persisted,
            background_tasks=background_tasks,
        )
        rent_response = hydrator.hydrate_rent(persisted)
        instructions = build_payment_instructions(
            self.db,
            persisted,
            field_summary=field_summary,
        )
        return RentPaymentResponse(
            rent=rent_response,
            payment_instructions=instructions,
        )

    def create_rent_admin(
        self,
        payload: RentAdminCreate,
        *,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> RentResponse:
        hydrator = RentHydrator(self.db)
        schedule = get_schedule(self.db, payload.id_schedule)
        ensure_schedule_not_started(schedule)
        ensure_schedule_available(
            self.db,
            schedule.id_schedule,
            excluded_statuses=self._active_excluded_statuses(),
        )
        raise_if_schedule_blocked_by_weekly_closure(self.db, schedule)
        self._ensure_field_window_clear_for_new_rent(
            schedule,
            exclude_schedule_id=schedule.id_schedule,
        )

        field_summary = (
            booking_reader.get_field_summary(self.db, schedule.id_field)
            if schedule.id_field is not None
            else None
        )

        rent_data = payload.model_dump(exclude_unset=True)
        status_code, status_id = resolve_status_pair(
            self.db,
            entity="rent",
            status_code=rent_data.get("status"),
            status_id=rent_data.get("id_status"),
        )
        rent_data["status"] = status_code
        rent_data["id_status"] = status_id
        rent_data.pop("start_time", None)
        rent_data.pop("end_time", None)

        rent_data.setdefault(
            "payment_deadline",
            compute_payment_deadline_from_schedule(schedule),
        )
        rent_data["customer_notes"] = apply_admin_note(
            rent_data.get("customer_notes")
        )

        ensure_admin_customer_fields(rent_data)

        apply_schedule_defaults(
            self.db,
            schedule=schedule,
            rent_data=rent_data,
            schedule_changed=True,
            field_summary=field_summary,
        )

        rent = rent_repository.create_rent(self.db, rent_data)
        rent_repository.add_rent_schedule_link(
            self.db,
            rent_id=rent.id_rent,
            schedule_id=schedule.id_schedule,
            is_primary=True,
        )
        schedule_code = (
            SCHEDULE_RESERVED_STATUS_CODE
            if (rent_data.get("status") or "").strip().lower() == RENT_RESERVED_STATUS_CODE
            else SCHEDULE_HOLD_PAYMENT_STATUS_CODE
        )
        schedule.status = schedule_code
        schedule.id_status = resolve_status_id(
            self.db,
            entity="schedule",
            code=schedule_code,
        )
        schedule_repository.save_schedule(self.db, schedule)

        refresh_field_status(
            self.db,
            schedule.id_field,
            excluded_statuses=self._active_excluded_statuses(),
        )

        if background_tasks is not None:
            background_tasks.add_task(
                reset_field_status_after_time,
                field_id=schedule.id_field,
                end_time=rent.end_time,
                excluded_statuses=self._active_excluded_statuses(),
            )

        persisted = rent_repository.get_rent(self.db, rent.id_rent)
        self._emit_rent_create_notifications(
            persisted,
            background_tasks=background_tasks,
        )
        return hydrator.hydrate_rent(persisted)

    def create_rent_combo(
        self,
        payload: RentCreateCombo,
        *,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> RentPaymentResponse:
        hydrator = RentHydrator(self.db)
        if payload.status != RENT_PENDING_PAYMENT_STATUS_CODE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Create rent only supports status 'pending_payment'",
            )

        combo = booking_reader.get_field_combination_for_reservation(
            self.db,
            payload.id_combination,
            active_only=True,
        )
        if combo is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Field combination not found or inactive",
            )

        ordered_schedules = validate_combo_schedules(
            self.db,
            member_field_ids=list(combo.member_field_ids),
            schedule_ids=payload.id_schedules,
            excluded_rent_statuses=self._active_excluded_statuses(),
        )
        primary = ordered_schedules[0]
        for sch in ordered_schedules:
            ensure_schedule_not_started(sch)
            ensure_schedule_available(
                self.db,
                sch.id_schedule,
                excluded_statuses=self._active_excluded_statuses(),
            )
            raise_if_schedule_blocked_by_weekly_closure(self.db, sch)
            self._ensure_field_window_clear_for_new_rent(
                sch,
                exclude_schedule_id=sch.id_schedule,
            )

        mount_override = compute_combo_mount_from_price_per_hour(
            price_per_hour=combo.price_per_hour,
            schedules=ordered_schedules,
        )

        field_summary = (
            booking_reader.get_field_summary(self.db, primary.id_field)
            if primary.id_field is not None
            else None
        )

        rent_data = payload.model_dump(exclude_unset=True)
        rent_data.pop("id_combination", None)
        rent_data.pop("id_schedules", None)
        status_code, status_id = resolve_status_pair(
            self.db,
            entity="rent",
            status_code=RENT_PENDING_PAYMENT_STATUS_CODE,
            status_id=rent_data.get("id_status"),
        )
        rent_data["status"] = status_code
        rent_data["id_status"] = status_id
        if not rent_data.get("payment_code"):
            rent_data["payment_code"] = generate_payment_code()
        rent_data.pop("start_time", None)
        rent_data.pop("end_time", None)
        rent_data.setdefault(
            "payment_deadline",
            compute_payment_deadline_from_schedule(primary),
        )

        apply_schedule_defaults(
            self.db,
            schedule=primary,
            rent_data=rent_data,
            schedule_changed=True,
            field_summary=field_summary,
            mount_override=mount_override,
        )

        if rent_data.get("id_payment") is not None:
            validate_payment(self.db, int(rent_data["id_payment"]))

        schedule_links = [
            (sch.id_schedule, sch.id_schedule == primary.id_schedule)
            for sch in ordered_schedules
        ]
        rent = rent_repository.create_rent_with_schedule_links(
            self.db,
            rent_data,
            schedule_links,
        )

        hold_status_id = resolve_status_id(
            self.db,
            entity="schedule",
            code=SCHEDULE_HOLD_PAYMENT_STATUS_CODE,
        )
        for sch in ordered_schedules:
            sch.status = SCHEDULE_HOLD_PAYMENT_STATUS_CODE
            sch.id_status = hold_status_id
            schedule_repository.save_schedule(self.db, sch)

        field_ids = {sch.id_field for sch in ordered_schedules if sch.id_field is not None}
        for fid in field_ids:
            refresh_field_status(
                self.db,
                fid,
                excluded_statuses=self._active_excluded_statuses(),
            )
        if background_tasks is not None:
            for fid in field_ids:
                background_tasks.add_task(
                    reset_field_status_after_time,
                    field_id=fid,
                    end_time=rent.end_time,
                    excluded_statuses=self._active_excluded_statuses(),
                )

        persisted = rent_repository.get_rent(self.db, rent.id_rent)
        self._emit_rent_create_notifications(
            persisted,
            background_tasks=background_tasks,
        )
        rent_response = hydrator.hydrate_rent(persisted)
        instructions = build_payment_instructions(
            self.db,
            persisted,
            field_summary=field_summary,
        )
        return RentPaymentResponse(
            rent=rent_response,
            payment_instructions=instructions,
        )

    def cancel_rent(self, rent_id: int, payload: RentCancelRequest) -> RentCancelResponse:
        rent: Optional[Rent] = rent_repository.get_rent(self.db, rent_id)

        if rent is None and payload.schedule_id is None:
            raise http_error(
                RENT_NOT_FOUND,
                detail="Rent not found",
            )

        schedule_ids_to_release: List[int] = []
        if rent is not None:
            schedule_ids_to_release = rent_repository.list_schedule_ids_for_rent(
                self.db, rent.id_rent
            )
            if not schedule_ids_to_release and rent.id_schedule is not None:
                schedule_ids_to_release = [rent.id_schedule]
        elif payload.schedule_id is not None:
            schedule_ids_to_release = [payload.schedule_id]

        if not schedule_ids_to_release:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="schedule_id is required when rent is not provided",
            )

        if rent is not None:
            status_value = (rent.status or "").lower()
            allowed_statuses = {value.lower() for value in RENT_HOLD_STATUS_CODES}
            if status_value not in allowed_statuses:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Rent cannot be cancelled in its current status",
                )
            rent.status = "cancelled"
            rent.id_status = resolve_status_id(self.db, entity="rent", code="cancelled")
            rent_repository.save_rent(self.db, rent)

        last_status = SCHEDULE_AVAILABLE_STATUS_CODE
        last_id: Optional[int] = None
        for sid in schedule_ids_to_release:
            sch = schedule_repository.get_schedule(self.db, sid)
            if sch is None:
                raise http_error(
                    SCHEDULE_NOT_FOUND,
                    detail="Schedule not found",
                )
            schedule_status_value = (sch.status or "").lower()
            if schedule_status_value != SCHEDULE_AVAILABLE_STATUS_CODE:
                if schedule_status_value not in {
                    SCHEDULE_HOLD_PAYMENT_STATUS_CODE,
                    SCHEDULE_PENDING_STATUS_CODE,
                }:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Schedule cannot be released in its current status",
                    )

                sch.status = SCHEDULE_AVAILABLE_STATUS_CODE
                sch.id_status = resolve_status_id(
                    self.db,
                    entity="schedule",
                    code=SCHEDULE_AVAILABLE_STATUS_CODE,
                )
                schedule_repository.save_schedule(self.db, sch)
            last_status = sch.status
            last_id = sch.id_schedule

        return RentCancelResponse(
            rent_id=rent.id_rent if rent is not None else None,
            rent_status=rent.status if rent is not None else None,
            schedule_id=last_id if last_id is not None else schedule_ids_to_release[0],
            schedule_status=last_status,
        )

    def update_rent(
        self,
        rent_id: int,
        payload: RentUpdate,
        *,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> RentResponse:
        hydrator = RentHydrator(self.db)
        rent = self._get_rent_model(rent_id)
        rent_had_id_payment_before = rent.id_payment is not None
        original_schedules = ordered_schedules_for_rent(self.db, rent)
        original_schedule = (
            original_schedules[0]
            if original_schedules
            else (get_schedule(self.db, rent.id_schedule) if rent.id_schedule else None)
        )
        original_field_ids = self._field_ids_for_rent(rent)
        original_status = (rent.status or "").strip().lower()

        update_data = payload.model_dump(exclude_unset=True)
        payment_submission_requested = (
            "id_payment" in update_data and update_data["id_payment"] is not None
        )
        if self._schedule_link_count(rent) > 1 and "id_schedule" in update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change schedule on a combined-field rent",
            )
        notify_after_payment = (
            "id_payment" in update_data
            and update_data["id_payment"] is not None
            and (rent.id_payment is None or rent.id_payment != update_data["id_payment"])
        )
        if payment_submission_requested:
            validate_payment(self.db, int(update_data["id_payment"]))
            if "status" in update_data:
                status_code, status_id = resolve_status_pair(
                    self.db,
                    entity="rent",
                    status_code=update_data.get("status"),
                    status_id=update_data.get("id_status"),
                )
                update_data["status"] = status_code
                update_data["id_status"] = status_id
            else:
                status_code, status_id = resolve_status_pair(
                    self.db,
                    entity="rent",
                    status_code=RENT_UNDER_REVIEW_STATUS_CODE,
                    status_id=update_data.get("id_status"),
                )
                update_data["status"] = status_code
                update_data["id_status"] = status_id
        elif "status" in update_data or "id_status" in update_data:
            status_code, status_id = resolve_status_pair(
                self.db,
                entity="rent",
                status_code=update_data.get("status"),
                status_id=update_data.get("id_status"),
            )
            update_data["status"] = status_code
            update_data["id_status"] = status_id

        target_schedule = original_schedule
        if target_schedule is None and rent.id_schedule is not None:
            target_schedule = get_schedule(self.db, rent.id_schedule)

        if "id_schedule" in update_data:
            target_schedule = get_schedule(self.db, update_data["id_schedule"])
            ensure_schedule_available(
                self.db,
                target_schedule.id_schedule,
                excluded_statuses=self._active_excluded_statuses(),
                exclude_rent_id=rent.id_rent,
            )
            raise_if_schedule_blocked_by_weekly_closure(self.db, target_schedule)
            self._ensure_field_window_clear_for_new_rent(
                target_schedule,
                exclude_schedule_id=target_schedule.id_schedule,
                exclude_rent_id=rent.id_rent,
            )

        if target_schedule is None:
            raise http_error(
                SCHEDULE_NOT_FOUND,
                detail="Associated schedule not found",
            )
        if payment_submission_requested:
            # User payment submissions are not allowed once the slot start time is reached.
            ensure_schedule_not_started(target_schedule)

        prev_primary = self._primary_schedule_id(rent)
        schedule_changed = prev_primary is None or target_schedule.id_schedule != prev_primary

        field_summary = (
            booking_reader.get_field_summary(self.db, target_schedule.id_field)
            if target_schedule.id_field is not None
            else None
        )
        mount_override = None
        if self._schedule_link_count(rent) > 1 and original_schedules:
            combo_price = booking_reader.find_field_combination_price_per_hour_by_fields(
                self.db,
                [sch.id_field for sch in original_schedules if sch.id_field is not None],
            )
            if combo_price is not None:
                mount_override = compute_combo_mount_from_price_per_hour(
                    price_per_hour=combo_price,
                    schedules=original_schedules,
                )
            else:
                mount_override = compute_combo_mount(schedules=original_schedules)

        apply_schedule_defaults(
            self.db,
            schedule=target_schedule,
            rent_data=update_data,
            schedule_changed=schedule_changed,
            existing_rent=rent,
            field_summary=field_summary,
            mount_override=mount_override,
        )

        for field, value in update_data.items():
            setattr(rent, field, value)

        if schedule_changed and self._schedule_link_count(rent) <= 1:
            rent_repository.sync_primary_schedule_link(
                self.db,
                rent_id=rent.id_rent,
                new_schedule_id=target_schedule.id_schedule,
            )

        rent_repository.save_rent(self.db, rent)
        updated_rent = rent_repository.get_rent(self.db, rent_id)
        self._emit_rent_update_notifications(
            updated_rent=updated_rent,
            original_status=original_status,
            rent_had_id_payment_before=rent_had_id_payment_before,
            notify_after_payment=notify_after_payment,
            is_admin_rent=False,
            background_tasks=background_tasks,
        )

        new_field_ids = self._field_ids_for_rent(updated_rent)
        for fid in set(original_field_ids) | set(new_field_ids):
            refresh_field_status(
                self.db,
                fid,
                excluded_statuses=self._active_excluded_statuses(),
            )

        if background_tasks is not None:
            for fid in new_field_ids:
                background_tasks.add_task(
                    reset_field_status_after_time,
                    field_id=fid,
                    end_time=updated_rent.end_time,
                    excluded_statuses=self._active_excluded_statuses(),
                )

        return hydrator.hydrate_rent(updated_rent)

    def update_rent_admin(
        self,
        rent_id: int,
        payload: RentAdminUpdate,
        *,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> RentResponse:
        hydrator = RentHydrator(self.db)
        rent = self._get_rent_model(rent_id)
        rent_had_id_payment_before = rent.id_payment is not None

        update_data = payload.model_dump(exclude_unset=True)
        if self._schedule_link_count(rent) > 1 and "id_schedule" in update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change schedule on a combined-field rent",
            )
        payment_submission_requested = (
            "id_payment" in update_data and update_data["id_payment"] is not None
        )
        if payment_submission_requested:
            validate_payment(self.db, int(update_data["id_payment"]))
        original_status = (rent.status or "").strip().lower()
        if "status" in update_data or "id_status" in update_data:
            status_code, status_id = resolve_status_pair(
                self.db,
                entity="rent",
                status_code=update_data.get("status"),
                status_id=update_data.get("id_status"),
            )
            update_data["status"] = status_code
            update_data["id_status"] = status_id

        original_schedules = ordered_schedules_for_rent(self.db, rent)
        target_schedule = (
            original_schedules[0]
            if original_schedules
            else (get_schedule(self.db, rent.id_schedule) if rent.id_schedule else None)
        )

        if "id_schedule" in update_data:
            target_schedule = get_schedule(self.db, update_data["id_schedule"])

        if target_schedule is None:
            raise http_error(
                SCHEDULE_NOT_FOUND,
                detail="Associated schedule not found",
            )

        ensure_schedule_available(
            self.db,
            target_schedule.id_schedule,
            excluded_statuses=self._active_excluded_statuses(),
            exclude_rent_id=rent.id_rent,
        )
        if "id_schedule" in update_data:
            raise_if_schedule_blocked_by_weekly_closure(self.db, target_schedule)
            self._ensure_field_window_clear_for_new_rent(
                target_schedule,
                exclude_schedule_id=target_schedule.id_schedule,
                exclude_rent_id=rent.id_rent,
            )

        prev_primary = self._primary_schedule_id(rent)
        schedule_changed = prev_primary is None or target_schedule.id_schedule != prev_primary
        next_status = (
            (update_data.get("status") or rent.status or "")
            .strip()
            .lower()
        )
        schedules_for_transition = self._schedules_for_admin_transition(
            rent=rent,
            original_schedules=original_schedules,
            target_schedule=target_schedule,
            schedule_changed=schedule_changed,
        )
        if next_status == RENT_RESERVED_STATUS_CODE:
            self._ensure_schedules_reusable_for_reservation(
                rent=rent,
                schedules=schedules_for_transition,
            )

        field_summary = (
            booking_reader.get_field_summary(self.db, target_schedule.id_field)
            if target_schedule.id_field is not None
            else None
        )
        mount_override = None
        if self._schedule_link_count(rent) > 1 and original_schedules:
            combo_price = booking_reader.find_field_combination_price_per_hour_by_fields(
                self.db,
                [sch.id_field for sch in original_schedules if sch.id_field is not None],
            )
            if combo_price is not None:
                mount_override = compute_combo_mount_from_price_per_hour(
                    price_per_hour=combo_price,
                    schedules=original_schedules,
                )
            else:
                mount_override = compute_combo_mount(schedules=original_schedules)

        update_data["customer_notes"] = apply_admin_note(
            update_data.get("customer_notes", rent.customer_notes)
        )

        ensure_admin_customer_fields(update_data, existing_rent=rent)

        apply_schedule_defaults(
            self.db,
            schedule=target_schedule,
            rent_data=update_data,
            schedule_changed=schedule_changed,
            existing_rent=rent,
            field_summary=field_summary,
            mount_override=mount_override,
        )

        for field, value in update_data.items():
            setattr(rent, field, value)

        if schedule_changed and self._schedule_link_count(rent) <= 1:
            rent_repository.sync_primary_schedule_link(
                self.db,
                rent_id=rent.id_rent,
                new_schedule_id=target_schedule.id_schedule,
            )

        if next_status == RENT_RESERVED_STATUS_CODE:
            self._set_schedules_status(
                schedules=schedules_for_transition,
                status_code=SCHEDULE_RESERVED_STATUS_CODE,
            )

        rent_repository.save_rent(self.db, rent)
        updated_rent = rent_repository.get_rent(self.db, rent_id)
        self._emit_rent_update_notifications(
            updated_rent=updated_rent,
            original_status=original_status,
            rent_had_id_payment_before=rent_had_id_payment_before,
            notify_after_payment=False,
            is_admin_rent=True,
            background_tasks=background_tasks,
        )

        for fid in self._field_ids_for_rent(updated_rent):
            refresh_field_status(
                self.db,
                fid,
                excluded_statuses=self._active_excluded_statuses(),
            )

        if background_tasks is not None:
            for fid in self._field_ids_for_rent(updated_rent):
                background_tasks.add_task(
                    reset_field_status_after_time,
                    field_id=fid,
                    end_time=updated_rent.end_time,
                    excluded_statuses=self._active_excluded_statuses(),
                )

        return hydrator.hydrate_rent(updated_rent)

    def delete_rent(self, rent_id: int) -> None:
        """Delete a rent from the database."""
        rent = self._get_rent_model(rent_id)
        field_ids = self._field_ids_for_rent(rent)
        rent_repository.delete_rent(self.db, rent)
        for fid in field_ids:
            refresh_field_status(
                self.db,
                fid,
                excluded_statuses=self._active_excluded_statuses(),
            )
