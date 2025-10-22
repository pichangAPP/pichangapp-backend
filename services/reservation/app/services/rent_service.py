from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.rent import Rent
from app.models.schedule import Schedule
from app.schemas.rent import RentCreate, RentUpdate


class RentService:

    _EXCLUDED_RENT_STATUSES = ("cancelled",)

    def __init__(self, db: Session):
        self.db = db

    def list_rents(
        self,
        *,
        status_filter: Optional[str] = None,
        schedule_id: Optional[int] = None,
    ) -> List[Rent]:

        query = self.db.query(Rent).options(
            joinedload(Rent.schedule).joinedload(Schedule.field),
            joinedload(Rent.schedule).joinedload(Schedule.user),
        )

        if status_filter is not None:
            query = query.filter(Rent.status == status_filter)
        if schedule_id is not None:
            query = query.filter(Rent.id_schedule == schedule_id)

        return query.order_by(Rent.start_time).all()

    def get_rent(self, rent_id: int) -> Rent:

        rent = (
            self.db.query(Rent)
            .options(
                joinedload(Rent.schedule).joinedload(Schedule.field),
                joinedload(Rent.schedule).joinedload(Schedule.user),
            )
            .filter(Rent.id_rent == rent_id)
            .first()
        )
        if rent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rent not found",
            )
        return rent

    def _get_schedule(self, schedule_id: int) -> Schedule:

        schedule = (
            self.db.query(Schedule)
            .options(
                joinedload(Schedule.field),
                joinedload(Schedule.user),
            )
            .filter(Schedule.id_schedule == schedule_id)
            .first()
        )
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

        query = self.db.query(Rent).filter(Rent.id_schedule == schedule_id)

        if exclude_rent_id is not None:
            query = query.filter(Rent.id_rent != exclude_rent_id)

        excluded_statuses = [
            status_value
            for status_value in self._EXCLUDED_RENT_STATUSES
            if status_value
        ]

        if excluded_statuses:
            lowered_statuses = [status_value.lower() for status_value in excluded_statuses]
            query = query.filter(func.lower(Rent.status).notin_(lowered_statuses))

        existing_rent = query.first()
        if existing_rent is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Schedule already has an active rent",
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
        self._apply_schedule_defaults(
            schedule=schedule,
            rent_data=rent_data,
            schedule_changed=True,
        )

        rent = Rent(**rent_data)
        self.db.add(rent)
        self.db.commit()
        return self.get_rent(rent.id_rent)

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

        for field, value in update_data.items():
            setattr(rent, field, value)

        self.db.commit()
        return self.get_rent(rent_id)

    def delete_rent(self, rent_id: int) -> None:
        """Delete a rent from the database."""

        rent = self.get_rent(rent_id)
        self.db.delete(rent)
        self.db.commit()
