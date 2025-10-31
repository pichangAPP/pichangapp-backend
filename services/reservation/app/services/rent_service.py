from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.rent import Rent
from app.models.schedule import Schedule
from app.repository import payment_repository, rent_repository, schedule_repository
from app.schemas.rent import RentCreate, RentUpdate


class RentService:

    _EXCLUDED_RENT_STATUSES = ("cancelled",)

    def __init__(self, db: Session):
        self.db = db

    def _ensure_field_exists(self, field_id: int) -> None:
        field = schedule_repository.get_field(self.db, field_id)
        if field is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated field not found",
            )

    def _ensure_user_exists(self, user_id: int) -> None:
        user = schedule_repository.get_user(self.db, user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated user not found",
            )

    def list_rents(
        self,
        *,
        status_filter: Optional[str] = None,
        schedule_id: Optional[int] = None,
    ) -> List[Rent]:

        return rent_repository.list_rents(
            self.db,
            status_filter=status_filter,
            schedule_id=schedule_id,
        )

    def list_rents_by_field(
        self,
        field_id: int,
        *,
        status_filter: Optional[str] = None,
    ) -> List[Rent]:

        self._ensure_field_exists(field_id)

        return rent_repository.list_rents(
            self.db,
            status_filter=status_filter,
            field_id=field_id,
        )

    def list_rents_by_user(
        self,
        user_id: int,
        *,
        status_filter: Optional[str] = None,
    ) -> List[Rent]:

        self._ensure_user_exists(user_id)

        return rent_repository.list_rents(
            self.db,
            status_filter=status_filter,
            user_id=user_id,
        )

    def list_user_rent_history(
        self,
        user_id: int,
        *,
        status_filter: Optional[str] = None,
    ) -> List[Rent]:

        self._ensure_user_exists(user_id)

        return rent_repository.list_rents(
            self.db,
            status_filter=status_filter,
            user_id=user_id,
            sort_desc=True,
        )

    def get_rent(self, rent_id: int) -> Rent:

        rent = rent_repository.get_rent(self.db, rent_id)
        if rent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rent not found",
            )
        return rent

    def _get_schedule(self, schedule_id: int) -> Schedule:

        schedule = schedule_repository.get_schedule(self.db, schedule_id)
        if schedule is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated schedule not found",
            )
        return schedule

    def _ensure_schedule_available(
        self,
        schedule_id: int,
        *,
        exclude_rent_id: Optional[int] = None,
    ) -> None:

        excluded_statuses = [
            status_value
            for status_value in self._EXCLUDED_RENT_STATUSES
            if status_value
        ]

        if rent_repository.schedule_has_active_rent(
            self.db,
            schedule_id,
            excluded_statuses=excluded_statuses,
            exclude_rent_id=exclude_rent_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Schedule already has an active rent",
            )

    def _validate_payment(self, payment_id: int) -> None:
        payment = payment_repository.get_payment(self.db, payment_id)
        if payment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated payment not found",
            )

        status_value = (payment.status or "").lower()
        if status_value != "paid":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment must be in paid status to link with the rent",
            )

    @staticmethod
    def _calculate_minutes(*, start_time: datetime, end_time: datetime) -> Decimal:

        duration = end_time - start_time
        if duration.total_seconds() <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Schedule end time must be after start time",
            )

        total_seconds = duration.days * 86400 + duration.seconds
        total_seconds_decimal = Decimal(total_seconds) + (
            Decimal(duration.microseconds) / Decimal(1_000_000)
        )
        minutes = total_seconds_decimal / Decimal(60)
        return minutes.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _format_period(minutes: Decimal) -> str:

        normalized_minutes = minutes.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        hours = int(normalized_minutes // Decimal(60))
        remaining_minutes = (
            normalized_minutes % Decimal(60)
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        segments = []
        if hours:
            segments.append(f"{hours} hour{'s' if hours != 1 else ''}")

        if remaining_minutes:
            remaining_is_int = remaining_minutes == remaining_minutes.to_integral()
            if remaining_is_int:
                minutes_value: str = str(int(remaining_minutes))
            else:
                minutes_value = format(remaining_minutes.normalize(), "f")
            segments.append(
                f"{minutes_value} minute{'s' if remaining_minutes != 1 else ''}"
            )

        if not segments:
            segments.append("0 minutes")

        return " ".join(segments)

    def _apply_schedule_defaults(
        self,
        *,
        schedule: Schedule,
        rent_data: Dict[str, object],
        schedule_changed: bool,
        existing_rent: Optional[Rent] = None,
    ) -> None:

        rent_data["id_schedule"] = schedule.id_schedule
        rent_data["start_time"] = schedule.start_time
        rent_data["end_time"] = schedule.end_time
        rent_data["mount"] = schedule.price

        minutes = self._calculate_minutes(
            start_time=schedule.start_time,
            end_time=schedule.end_time,
        )
        rent_data["minutes"] = minutes

        if schedule_changed or existing_rent is None:
            rent_data.setdefault("initialized", schedule.start_time)
            rent_data.setdefault("finished", schedule.end_time)
            rent_data.setdefault("date_log", schedule.start_time)
        else:
            if "initialized" not in rent_data:
                rent_data["initialized"] = existing_rent.initialized
            if "finished" not in rent_data:
                rent_data["finished"] = existing_rent.finished
            if "date_log" not in rent_data:
                rent_data["date_log"] = existing_rent.date_log

        if "capacity" not in rent_data or rent_data["capacity"] is None:
            capacity_source = None
            if schedule.field is not None:
                capacity_source = schedule.field.capacity
            elif existing_rent is not None:
                capacity_source = existing_rent.capacity

            if capacity_source is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Unable to determine capacity for rent. Provide the "
                        "capacity explicitly or associate the schedule with a field."
                    ),
                )

            rent_data["capacity"] = capacity_source

        if "period" not in rent_data or rent_data["period"] is None:
            if existing_rent is not None and not schedule_changed:
                rent_data["period"] = existing_rent.period
            else:
                rent_data["period"] = self._format_period(minutes)

    def create_rent(self, payload: RentCreate) -> Rent:

        schedule = self._get_schedule(payload.id_schedule)
        self._ensure_schedule_available(schedule.id_schedule)

        rent_data = payload.dict(exclude_unset=True)
        rent_data.setdefault(
            "payment_deadline",
            datetime.now(timezone.utc) + timedelta(minutes=5),
        )

        self._apply_schedule_defaults(
            schedule=schedule,
            rent_data=rent_data,
            schedule_changed=True,
        )

        if rent_data.get("id_payment") is not None:
            self._validate_payment(int(rent_data["id_payment"]))

        rent = rent_repository.create_rent(self.db, rent_data)
        return rent_repository.get_rent(self.db, rent.id_rent)

    def update_rent(self, rent_id: int, payload: RentUpdate) -> Rent:
        """Update an existing rent."""

        rent = self.get_rent(rent_id)

        update_data = payload.dict(exclude_unset=True)

        target_schedule = rent.schedule or self._get_schedule(rent.id_schedule)

        if "id_schedule" in update_data:
            target_schedule = self._get_schedule(update_data["id_schedule"])
            self._ensure_schedule_available(
                target_schedule.id_schedule,
                exclude_rent_id=rent.id_rent,
            )

        schedule_changed = target_schedule.id_schedule != rent.id_schedule

        self._apply_schedule_defaults(
            schedule=target_schedule,
            rent_data=update_data,
            schedule_changed=schedule_changed,
            existing_rent=rent,
        )

        if "id_payment" in update_data and update_data["id_payment"] is not None:
            self._validate_payment(int(update_data["id_payment"]))

        for field, value in update_data.items():
            setattr(rent, field, value)

        rent_repository.save_rent(self.db, rent)
        return rent_repository.get_rent(self.db, rent_id)

    def delete_rent(self, rent_id: int) -> None:
        """Delete a rent from the database."""

        rent = self.get_rent(rent_id)
        rent_repository.delete_rent(self.db, rent)
