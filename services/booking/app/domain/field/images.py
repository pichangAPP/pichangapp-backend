from __future__ import annotations

from app.core.error_codes import BOOKING_BAD_REQUEST, BOOKING_NOT_FOUND, http_error
from app.core.image_url_validation import validate_https_image_url, validate_image_url_in_mapping
from app.models import Field, Image
from app.repository import image_repository


def sync_field_images(
    db, field: Field, images_data: list[dict[str, object]]
) -> None:
    """Sincroniza las imagenes asociadas a una cancha existente.

    Usado en: FieldService.update_field.
    """
    existing_images_by_id = {
        image.id_image: image for image in field.images if image.id_image is not None
    }
    incoming_ids: set[int] = set()

    for image_data in images_data:
        id_field = image_data.get("id_field")
        if id_field != field.id_field:
            raise http_error(
                BOOKING_BAD_REQUEST,
                detail="Image field id must match the field being updated",
            )

        image_id = image_data.get("id_image")
        if image_id is not None:
            image = existing_images_by_id.get(image_id)
            if image is None:
                raise http_error(
                    BOOKING_NOT_FOUND,
                    detail=f"Image {image_id} not found for field {field.id_field}",
                )
            incoming_ids.add(image_id)
            updated_fields = {
                key: value for key, value in image_data.items() if key != "id_image"
            }
            for attr, value in updated_fields.items():
                if attr == "image_url" and value is not None:
                    normalized_url = str(value).strip()
                    current_url = (image.image_url or "").strip()
                    try:
                        if normalized_url != current_url:
                            validate_https_image_url(normalized_url)
                    except ValueError as exc:
                        raise http_error(BOOKING_BAD_REQUEST, detail=str(exc)) from exc
                    value = normalized_url
                setattr(image, attr, value)
        else:
            new_image_data = {
                key: value for key, value in image_data.items() if key != "id_image"
            }
            try:
                validate_image_url_in_mapping(new_image_data)
            except ValueError as exc:
                raise http_error(BOOKING_BAD_REQUEST, detail=str(exc)) from exc
            field.images.append(Image(**new_image_data))

    for image in list(field.images):
        if image.id_image is not None and image.id_image not in incoming_ids:
            field.images.remove(image)
            image_repository.delete_image(db, image)


def add_images_to_new_field(field: Field, images_data: list[object]) -> None:
    """Agrega imagenes a una cancha nueva usando las validaciones actuales.

    Usado en: FieldService.create_field.
    """
    for image_in in images_data:
        image_payload = (
            image_in.model_dump()
            if hasattr(image_in, "model_dump")
            else dict(image_in)
        )
        validated_payload = validate_new_field_image(field, image_payload)
        validated_payload["id_field"] = field.id_field
        validated_payload["id_campus"] = field.id_campus
        field.images.append(Image(**validated_payload))


def validate_new_field_image(field: Field, image_data: dict[str, object]) -> dict[str, object]:
    """Valida el payload de una imagen al crear una cancha.

    Usado en: FieldService.create_field (via add_images_to_new_field).
    """
    id_field = image_data.get("id_field")
    if id_field is not None and id_field != field.id_field:
        raise http_error(
            BOOKING_BAD_REQUEST,
            detail="Image field id must match the field being created",
        )
    id_campus = image_data.get("id_campus")
    if id_campus is not None and id_campus != field.id_campus:
        raise http_error(
            BOOKING_BAD_REQUEST,
            detail="Image campus id must match the parent campus",
        )
    image_type = image_data.get("type")
    if image_type != "field":
        raise http_error(
            BOOKING_BAD_REQUEST,
            detail="Field images must have type 'field'",
        )
    try:
        validate_image_url_in_mapping(dict(image_data))
    except ValueError as exc:
        raise http_error(BOOKING_BAD_REQUEST, detail=str(exc)) from exc
    return image_data
