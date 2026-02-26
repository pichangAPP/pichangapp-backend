import asyncio
from datetime import datetime, timedelta, timezone
import logging
from decimal import Decimal, ROUND_HALF_UP
from email.utils import parseaddr
import re
import secrets
import string
from typing import Dict, List, Optional, Sequence

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.status_constants import (
    RENT_FINAL_STATUS_CODES,
    RENT_PENDING_PAYMENT_STATUS_CODE,
    SCHEDULE_HOLD_PAYMENT_STATUS_CODE,
)
from app.integrations import auth_reader, booking_reader, payment_reader
from app.models.rent import Rent
from app.models.schedule import Schedule
from app.repository import rent_repository, schedule_repository, status_catalog_repository
from app.schemas.rent import (
    PaymentInstructions,
    RentAdminCreate,
    RentAdminUpdate,
    RentCreate,
    RentPaymentResponse,
    RentResponse,
    RentUpdate,
    ScheduleSummary,
)
from app.schemas.schedule import FieldSummary, UserSummary
from app.services.notification_client import NotificationClient

logger = logging.getLogger(__name__)


class RentService:

    _EXCLUDED_RENT_STATUSES = RENT_FINAL_STATUS_CODES
    _FIELD_STATUS_ACTIVE = "active"
    _FIELD_STATUS_OCCUPIED = "occupied"
    _ADMIN_NOTE = "Creado por administrador"
    _EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    def __init__(
        self,
        db: Session,
        *,
        notification_client: Optional[NotificationClient] = None,
    ):
        self.db = db
        self._notification_client = notification_client or NotificationClient()

    @staticmethod
    def _datetime_to_iso(value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        return value.isoformat()

    @staticmethod
    def _decimal_to_str(value: Optional[Decimal]) -> Optional[str]:
        if value is None:
            return None
        return format(value, "f")

    @classmethod
    def _is_valid_email(cls, value: Optional[str]) -> bool:
        if not value:
            return False
        _, addr = parseaddr(value)
        if addr != value:
            return False
        return bool(cls._EMAIL_REGEX.match(value))

    @staticmethod
    def _split_full_name(full_name: Optional[str]) -> tuple[str, str]:
        if not full_name:
            return "", ""
        parts = full_name.strip().split()
        if not parts:
            return "", ""
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], " ".join(parts[1:])

    def _resolve_status_pair(
        self,
        *,
        entity: str,
        status_code: Optional[str],
        status_id: Optional[int],
    ) -> tuple[str, int]:
        if status_id is not None:
            status_item = status_catalog_repository.get_status(self.db, status_id)
            if status_item is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Status id {status_id} is not defined in status_catalog",
                )
            if status_item.entity != entity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Status id {status_id} does not belong to entity {entity!r}"
                    ),
                )
            if status_code is not None and status_item.code != status_code:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Status id {status_id} does not match status {status_code!r} "
                        f"for entity {entity!r}"
                    ),
                )
            return status_item.code, int(status_item.id_status)

        if status_code is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="status or id_status must be provided",
            )

        return status_code, self._resolve_status_id(entity, status_code)

    def _resolve_status_id(self, entity: str, code: str) -> int:
        status_item = status_catalog_repository.get_status_by_entity_code(
            self.db,
            entity=entity,
            code=code,
        )
        if status_item is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Status code {code!r} for entity {entity!r} "
                    "is not defined in status_catalog"
                ),
            )
        return int(status_item.id_status)

    @staticmethod
    def _generate_payment_code(length: int = 6) -> str:
        alphabet = string.ascii_uppercase + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def _build_payment_instructions(
        self,
        rent: Rent,
        *,
        field_summary: Optional[FieldSummary],
    ) -> PaymentInstructions:
        wallet_info = None
        if field_summary is not None:
            wallet_info = payment_reader.get_campus_digital_wallets(
                self.db, campus_id=field_summary.id_campus
            )

        if not wallet_info:
            return PaymentInstructions(
                payment_code=rent.payment_code or "",
                message="Realiza el pago y sube la captura para continuar.",
            )

        has_yape = bool(wallet_info.get("yape_phone") or wallet_info.get("yape_qr_url"))
        has_plin = bool(wallet_info.get("plin_phone") or wallet_info.get("plin_qr_url"))
        if has_yape and has_plin:
            message = "Realiza el pago por Yape o Plin y sube la captura para continuar."
        elif has_yape:
            message = "Realiza el pago por Yape y sube la captura para continuar."
        elif has_plin:
            message = "Realiza el pago por Plin y sube la captura para continuar."
        else:
            message = "Realiza el pago y sube la captura para continuar."

        return PaymentInstructions(
            yape_phone=wallet_info.get("yape_phone") if has_yape else None,
            yape_qr_url=wallet_info.get("yape_qr_url") if has_yape else None,
            plin_phone=wallet_info.get("plin_phone") if has_plin else None,
            plin_qr_url=wallet_info.get("plin_qr_url") if has_plin else None,
            payment_code=rent.payment_code or "",
            message=message,
            status=wallet_info.get("status"),
            created_at=wallet_info.get("created_at"),
            updated_at=wallet_info.get("updated_at"),
        )

    def _build_notification_payload(self, rent: Rent) -> Optional[Dict[str, object]]:
        schedule = rent.schedule
        if schedule is None or schedule.id_field is None:
            logger.info(
                "Skipping notification payload creation for rent %s due to missing schedule data",
                rent.id_rent,
            )
            return None

        field = booking_reader.get_field_summary(self.db, schedule.id_field)
        if field is None:
            logger.info(
                "Skipping notification payload creation for rent %s due to missing external data",
                rent.id_rent,
            )
            return None

        if schedule.id_user is not None:
            try:
                user = auth_reader.get_user_summary(self.db, schedule.id_user)
            except auth_reader.AuthReaderError as exc:
                logger.warning(
                    "Auth service unavailable while building notification payload: %s",
                    exc,
                )
                return None
            if user is None:
                logger.info(
                    "Skipping notification payload creation for rent %s due to missing user data",
                    rent.id_rent,
                )
                return None
            if not self._is_valid_email(user.email):
                logger.info(
                    "Skipping notification payload creation for rent %s due to invalid user email",
                    rent.id_rent,
                )
                return None
            user_payload = {
                "name": user.name,
                "lastname": user.lastname,
                "email": user.email,
            }
        else:
            if not self._is_valid_email(rent.customer_email):
                logger.info(
                    "Skipping notification payload creation for rent %s due to invalid customer email",
                    rent.id_rent,
                )
                return None
            name, lastname = self._split_full_name(rent.customer_full_name)
            user_payload = {
                "name": name or "Cliente",
                "lastname": lastname,
                "email": rent.customer_email,
            }

        campus = booking_reader.get_campus_summary(self.db, field.id_campus)
        if campus is None:
            logger.info(
                "Skipping notification payload creation for rent %s because campus information is missing",
                rent.id_rent,
            )
            return None

        campus_payload = {
            "id_campus": campus.id_campus,
            "name": campus.name,
            "address": campus.address,
            "district": campus.district,
        }

        manager_payload = None
        if campus.id_manager is not None:
            try:
                manager = auth_reader.get_user_summary(self.db, campus.id_manager)
            except auth_reader.AuthReaderError as exc:
                logger.warning(
                    "Auth service unavailable while fetching manager for rent %s: %s",
                    rent.id_rent,
                    exc,
                )
                manager = None
        else:
            manager = None
        if manager is not None and manager.email:
            manager_payload = {
                "name": manager.name,
                "lastname": manager.lastname,
                "email": manager.email,
            }

        return {
            "rent": {
                "rent_id": rent.id_rent,
                "schedule_day": schedule.day_of_week,
                "start_time": self._datetime_to_iso(rent.start_time),
                "end_time": self._datetime_to_iso(rent.end_time),
                "status": rent.status,
                "period": rent.period,
                "mount": self._decimal_to_str(rent.mount),
                "payment_deadline": self._datetime_to_iso(rent.payment_deadline),
                "field_name": field.field_name,
                "campus": campus_payload,
            },
            "user": {
                "name": user_payload["name"],
                "lastname": user_payload["lastname"],
                "email": user_payload["email"],
            },
            "manager": manager_payload,
        }

    def _notify_rent_creation(self, rent: Rent) -> None:
        payload = self._build_notification_payload(rent)
        if payload is None:
            return
        logger.info("Dispatching rent notification for rent %s", rent.id_rent)
        self._notification_client.send_rent_email(payload)

    def _ensure_field_exists(self, field_id: int) -> None:
        field = booking_reader.get_field_summary(self.db, field_id)
        if field is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated field not found",
            )

    def _ensure_user_exists(self, user_id: int) -> None:
        try:
            user = auth_reader.get_user_summary(self.db, user_id)
        except auth_reader.AuthReaderError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
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
    ) -> List[RentResponse]:

        rents = rent_repository.list_rents(
            self.db,
            status_filter=status_filter,
            schedule_id=schedule_id,
        )
        return self._hydrate_rents(rents)

    def list_rents_by_campus(
        self,
        campus_id: int,
        *,
        status_filter: Optional[str] = None,
    ) -> List[RentResponse]:
        rows = rent_repository.list_rents_by_campus_view(
            self.db,
            campus_id=campus_id,
            status_filter=status_filter,
        )
        return self._build_rent_responses_from_rows(rows)

    def list_rents_by_field(
        self,
        field_id: int,
        *,
        status_filter: Optional[str] = None,
    ) -> List[RentResponse]:

        self._ensure_field_exists(field_id)

        rents = rent_repository.list_rents(
            self.db,
            status_filter=status_filter,
            field_id=field_id,
        )
        return self._hydrate_rents(rents)

    def list_rents_by_user(
        self,
        user_id: int,
        *,
        status_filter: Optional[str] = None,
    ) -> List[RentResponse]:

        self._ensure_user_exists(user_id)

        rents = rent_repository.list_rents(
            self.db,
            status_filter=status_filter,
            user_id=user_id,
        )
        return self._hydrate_rents(rents)

    def list_user_rent_history(
        self,
        user_id: int,
        *,
        status_filter: Optional[str] = None,
    ) -> List[RentResponse]:

        self._ensure_user_exists(user_id)

        rents = rent_repository.list_rents(
            self.db,
            status_filter=status_filter,
            user_id=user_id,
            sort_desc=True,
        )
        return self._hydrate_rents(rents)

    def _get_rent_model(self, rent_id: int) -> Rent:

        rent = rent_repository.get_rent(self.db, rent_id)
        if rent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rent not found",
            )
        return rent

    def get_rent(self, rent_id: int) -> RentResponse:
        rent = self._get_rent_model(rent_id)
        return self._hydrate_rent(rent)

    def _hydrate_rent(self, rent: Optional[Rent]) -> RentResponse:
        if rent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rent not found",
            )
        return self._hydrate_rents([rent])[0]

    def _hydrate_rents(self, rents: Sequence[Rent]) -> List[RentResponse]:
        schedules: List[Schedule] = []
        for rent in rents:
            schedule = rent.schedule or schedule_repository.get_schedule(
                self.db, rent.id_schedule
            )
            if schedule is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Associated schedule not found",
                )
            rent.schedule = schedule
            schedules.append(schedule)

        field_ids = [schedule.id_field for schedule in schedules if schedule.id_field]
        user_ids = [schedule.id_user for schedule in schedules if schedule.id_user]

        fields = booking_reader.get_field_summaries(self.db, field_ids)
        try:
            users = auth_reader.get_user_summaries(self.db, user_ids)
        except auth_reader.AuthReaderError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

        responses: List[RentResponse] = []
        for rent in rents:
            schedule = rent.schedule
            field = fields.get(schedule.id_field)
            user = users.get(schedule.id_user)
            schedule_summary = self._build_schedule_summary(
                schedule,
                field=field,
                user=user,
            )
            responses.append(self._build_rent_response(rent, schedule_summary))
        return responses

    def _build_rent_responses_from_rows(self, rows: Sequence[dict]) -> List[RentResponse]:
        responses: List[RentResponse] = []
        for row in rows:
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
            schedule_summary = ScheduleSummary(
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
            responses.append(
                RentResponse(
                    id_rent=row["id_rent"],
                    period=row["period"],
                    start_time=row["start_time"],
                    end_time=row["end_time"],
                    initialized=row["initialized"],
                    finished=row["finished"],
                    status=row["status"],
                    id_status=row.get("rent_id_status"),
                    minutes=row["minutes"],
                    mount=row["mount"],
                    date_log=row["date_log"],
                    date_create=row["date_create"],
                    payment_deadline=row["payment_deadline"],
                    capacity=row["capacity"],
                    id_payment=row["id_payment"],
                    payment_code=row.get("payment_code"),
                    payment_proof_url=row.get("payment_proof_url"),
                    payment_reviewed_at=row.get("payment_reviewed_at"),
                    payment_reviewed_by=row.get("payment_reviewed_by"),
                    customer_full_name=row.get("customer_full_name"),
                    customer_phone=row.get("customer_phone"),
                    customer_email=row.get("customer_email"),
                    customer_document=row.get("customer_document"),
                    customer_notes=row.get("customer_notes"),
                    id_schedule=row["id_schedule"],
                    schedule=schedule_summary,
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
        if field is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
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
        schedule: ScheduleSummary,
    ) -> RentPaymentResponse:
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
            id_schedule=rent.id_schedule,
            schedule=schedule,
        )

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
        payment_status = payment_reader.get_payment_status(self.db, payment_id)
        if payment_status is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated payment not found",
            )

        status_value = (payment_status or "").lower()
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
        field_summary: Optional[FieldSummary] = None,
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
            if field_summary is None and schedule.id_field is not None:
                field_summary = booking_reader.get_field_summary(
                    self.db, schedule.id_field
                )
            if field_summary is not None:
                capacity_source = field_summary.capacity
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

    @classmethod
    def _apply_admin_note(cls, notes: Optional[str]) -> str:
        if not notes:
            return cls._ADMIN_NOTE
        if cls._ADMIN_NOTE.lower() in notes.lower():
            return notes
        return f"{notes}\n{cls._ADMIN_NOTE}"

    def _ensure_admin_customer_fields(
        self,
        rent_data: Dict[str, object],
        *,
        existing_rent: Optional[Rent] = None,
    ) -> None:
        required_fields = (
            "customer_full_name",
        )
        missing = []
        for field in required_fields:
            value = rent_data.get(field)
            if value is None and existing_rent is not None:
                value = getattr(existing_rent, field, None)
            if not value:
                missing.append(field)
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing admin customer fields: {', '.join(missing)}",
            )

    def create_rent(
        self,
        payload: RentCreate,
        *,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> RentPaymentResponse:

        if payload.status != RENT_PENDING_PAYMENT_STATUS_CODE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Create rent only supports status 'pending_payment'",
            )

        schedule = self._get_schedule(payload.id_schedule)
        self._ensure_schedule_available(schedule.id_schedule)
        field_summary = (
            booking_reader.get_field_summary(self.db, schedule.id_field)
            if schedule.id_field is not None
            else None
        )

        # Build the rent from the schedule definition
        # so start/end/pricing.
        rent_data = payload.dict(exclude_unset=True)
        status_code, status_id = self._resolve_status_pair(
            entity="rent",
            status_code=RENT_PENDING_PAYMENT_STATUS_CODE,
            status_id=rent_data.get("id_status"),
        )
        rent_data["status"] = status_code
        rent_data["id_status"] = status_id
        if not rent_data.get("payment_code"):
            rent_data["payment_code"] = self._generate_payment_code()
        rent_data.pop("start_time", None)
        rent_data.pop("end_time", None)

        rent_data.setdefault(
            "payment_deadline",
            datetime.now(timezone.utc) + timedelta(minutes=5),
        )


        self._apply_schedule_defaults(
            schedule=schedule,
            rent_data=rent_data,
            schedule_changed=True,
            field_summary=field_summary,
        )

        if rent_data.get("id_payment") is not None:
            self._validate_payment(int(rent_data["id_payment"]))

        rent = rent_repository.create_rent(self.db, rent_data)
        schedule.status = SCHEDULE_HOLD_PAYMENT_STATUS_CODE
        schedule.id_status = self._resolve_status_id(
            "schedule", SCHEDULE_HOLD_PAYMENT_STATUS_CODE
        )
        schedule_repository.save_schedule(self.db, schedule)
        persisted_rent = rent_repository.get_rent(self.db, rent.id_rent)
        if persisted_rent is not None:
            self._notify_rent_creation(persisted_rent)
            rent_response = self._hydrate_rent(persisted_rent)
            instructions = self._build_payment_instructions(
                persisted_rent,
                field_summary=field_summary,
            )
            return RentPaymentResponse(
                rent=rent_response,
                payment_instructions=instructions,
            )
    
        self._refresh_field_status(self.db, schedule.id_field)

        if background_tasks is not None:
            background_tasks.add_task(
                self._reset_field_status_after_time,
                schedule.id_field,
                rent.end_time,
            )

        persisted = rent_repository.get_rent(self.db, rent.id_rent)
        rent_response = self._hydrate_rent(persisted)
        instructions = self._build_payment_instructions(
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

        schedule = self._get_schedule(payload.id_schedule)
        self._ensure_schedule_available(schedule.id_schedule)

        field_summary = (
            booking_reader.get_field_summary(self.db, schedule.id_field)
            if schedule.id_field is not None
            else None
        )

        rent_data = payload.dict(exclude_unset=True)
        status_code, status_id = self._resolve_status_pair(
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
            datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        rent_data["customer_notes"] = self._apply_admin_note(
            rent_data.get("customer_notes")
        )

        self._ensure_admin_customer_fields(rent_data)

        self._apply_schedule_defaults(
            schedule=schedule,
            rent_data=rent_data,
            schedule_changed=True,
            field_summary=field_summary,
        )

        rent = rent_repository.create_rent(self.db, rent_data)
        schedule.status = SCHEDULE_HOLD_PAYMENT_STATUS_CODE
        schedule.id_status = self._resolve_status_id(
            "schedule", SCHEDULE_HOLD_PAYMENT_STATUS_CODE
        )
        schedule_repository.save_schedule(self.db, schedule)

        persisted_rent = rent_repository.get_rent(self.db, rent.id_rent)
        if persisted_rent is not None:
            self._notify_rent_creation(persisted_rent)
            return self._hydrate_rent(persisted_rent)

        self._refresh_field_status(self.db, schedule.id_field)

        if background_tasks is not None:
            background_tasks.add_task(
                self._reset_field_status_after_time,
                schedule.id_field,
                rent.end_time,
            )

        persisted = rent_repository.get_rent(self.db, rent.id_rent)
        return self._hydrate_rent(persisted)

    def update_rent(
        self,
        rent_id: int,
        payload: RentUpdate,
        *,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> RentResponse:
        """Update an existing rent."""

        rent = self._get_rent_model(rent_id)
        original_schedule = rent.schedule or self._get_schedule(rent.id_schedule)
        original_field_id = original_schedule.id_field if original_schedule else None

        update_data = payload.dict(exclude_unset=True)
        if "status" in update_data or "id_status" in update_data:
            status_code, status_id = self._resolve_status_pair(
                entity="rent",
                status_code=update_data.get("status"),
                status_id=update_data.get("id_status"),
            )
            update_data["status"] = status_code
            update_data["id_status"] = status_id

        target_schedule = rent.schedule or self._get_schedule(rent.id_schedule)

        if "id_schedule" in update_data:
            target_schedule = self._get_schedule(update_data["id_schedule"])
            self._ensure_schedule_available(
                target_schedule.id_schedule,
                exclude_rent_id=rent.id_rent,
            )

        schedule_changed = target_schedule.id_schedule != rent.id_schedule

        field_summary = (
            booking_reader.get_field_summary(self.db, target_schedule.id_field)
            if target_schedule.id_field is not None
            else None
        )

        self._apply_schedule_defaults(
            schedule=target_schedule,
            rent_data=update_data,
            schedule_changed=schedule_changed,
            existing_rent=rent,
            field_summary=field_summary,
        )

        if "id_payment" in update_data and update_data["id_payment"] is not None:
            self._validate_payment(int(update_data["id_payment"]))

        for field, value in update_data.items():
            setattr(rent, field, value)

        rent_repository.save_rent(self.db, rent)
        updated_rent = rent_repository.get_rent(self.db, rent_id)

        self._refresh_field_status(self.db, original_field_id)

        new_field_id = (
            updated_rent.schedule.id_field if updated_rent.schedule is not None else None
        )
        if new_field_id != original_field_id:
            self._refresh_field_status(self.db, new_field_id)

        if background_tasks is not None:
            background_tasks.add_task(
                self._reset_field_status_after_time,
                new_field_id,
                updated_rent.end_time,
            )

        return self._hydrate_rent(updated_rent)

    def update_rent_admin(
        self,
        rent_id: int,
        payload: RentAdminUpdate,
        *,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> RentResponse:

        rent = self._get_rent_model(rent_id)

        update_data = payload.dict(exclude_unset=True)
        if "status" in update_data or "id_status" in update_data:
            status_code, status_id = self._resolve_status_pair(
                entity="rent",
                status_code=update_data.get("status"),
                status_id=update_data.get("id_status"),
            )
            update_data["status"] = status_code
            update_data["id_status"] = status_id

        target_schedule = rent.schedule or self._get_schedule(rent.id_schedule)

        if "id_schedule" in update_data:
            target_schedule = self._get_schedule(update_data["id_schedule"])

        self._ensure_schedule_available(
            target_schedule.id_schedule,
            exclude_rent_id=rent.id_rent,
        )

        schedule_changed = target_schedule.id_schedule != rent.id_schedule

        field_summary = (
            booking_reader.get_field_summary(self.db, target_schedule.id_field)
            if target_schedule.id_field is not None
            else None
        )

        update_data["customer_notes"] = self._apply_admin_note(
            update_data.get("customer_notes", rent.customer_notes)
        )

        self._ensure_admin_customer_fields(update_data, existing_rent=rent)

        self._apply_schedule_defaults(
            schedule=target_schedule,
            rent_data=update_data,
            schedule_changed=schedule_changed,
            existing_rent=rent,
            field_summary=field_summary,
        )

        for field, value in update_data.items():
            setattr(rent, field, value)

        rent_repository.save_rent(self.db, rent)
        updated_rent = rent_repository.get_rent(self.db, rent_id)

        self._refresh_field_status(self.db, target_schedule.id_field)

        if background_tasks is not None:
            background_tasks.add_task(
                self._reset_field_status_after_time,
                target_schedule.id_field,
                updated_rent.end_time,
            )

        return self._hydrate_rent(updated_rent)

    def delete_rent(self, rent_id: int) -> None:
        """Delete a rent from the database."""

        rent = self._get_rent_model(rent_id)
        field_id = rent.schedule.id_field if rent.schedule is not None else None
        rent_repository.delete_rent(self.db, rent)
        self._refresh_field_status(self.db, field_id)

    @staticmethod
    def _refresh_field_status(db: Session, field_id: Optional[int]) -> None:
        if field_id is None:
            return

        field = booking_reader.get_field_summary(db, field_id)
        if field is None:
            return

        has_pending_rent = rent_repository.field_has_pending_rent(
            db,
            field_id,
            excluded_statuses=RentService._EXCLUDED_RENT_STATUSES,
        )

        target_status = (
            RentService._FIELD_STATUS_OCCUPIED
            if has_pending_rent
            else RentService._FIELD_STATUS_ACTIVE
        )

        current_status = (field.status or "").strip().lower()
        if current_status == target_status:
            return

        booking_reader.update_field_status(db, field_id, target_status)

    @staticmethod
    async def _reset_field_status_after_time(
        field_id: Optional[int],
        end_time: Optional[datetime],
    ) -> None:
        if field_id is None or end_time is None:
            return

        if end_time.tzinfo is None:
            target_end = end_time.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
        else:
            target_end = end_time
            now = datetime.now(target_end.tzinfo)

        delay = (target_end - now).total_seconds()
        if delay > 0:
            await asyncio.sleep(delay)

        db = SessionLocal()
        try:
            RentService._refresh_field_status(db, field_id)
        finally:
            db.close()
