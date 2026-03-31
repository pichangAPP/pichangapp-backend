"""Dominio de booking para reglas y utilidades compartidas."""

from app.domain.business import (
    attach_business_manager_data,
    get_business_or_error,
    validate_business_entity,
)
from app.domain.campus import (
    attach_campus_manager_data,
    build_campus_entity,
    populate_available_schedules,
    sync_campus_images,
    update_campus_field_count,
    validate_campus_entity,
    validate_campus_fields,
)
from app.domain.field import (
    add_images_to_new_field,
    ensure_field_deletable,
    ensure_sport_exists,
    populate_next_available_time_range,
    sync_field_images,
    validate_field_entity,
    validate_new_field_image,
)

__all__ = [
    "add_images_to_new_field",
    "attach_business_manager_data",
    "attach_campus_manager_data",
    "build_campus_entity",
    "ensure_field_deletable",
    "ensure_sport_exists",
    "get_business_or_error",
    "populate_available_schedules",
    "populate_next_available_time_range",
    "sync_campus_images",
    "sync_field_images",
    "update_campus_field_count",
    "validate_business_entity",
    "validate_campus_entity",
    "validate_campus_fields",
    "validate_field_entity",
    "validate_new_field_image",
]
