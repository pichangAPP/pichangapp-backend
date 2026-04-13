from __future__ import annotations

from app.core.error_codes import BOOKING_BAD_REQUEST, BOOKING_NOT_FOUND, http_error
from app.core.image_url_validation import validate_https_image_url, validate_image_url_in_mapping
from app.models import Campus, Image
from app.repository import image_repository


def sync_campus_images(
    db, campus: Campus, images_data: list[dict[str, object]]
) -> None:
    """Sincroniza las imagenes del campus con el payload recibido.

    Usado en: CampusService.update_campus.
    """
    campus_images = [image for image in campus.images if image.id_field is None]
    existing_images_by_id = {
        image.id_image: image
        for image in campus_images
        if image.id_image is not None
    }
    incoming_ids: set[int] = set()

    for image_data in images_data:
        try:
            validate_image_url_in_mapping(dict(image_data))
        except ValueError as exc:
            raise http_error(BOOKING_BAD_REQUEST, detail=str(exc)) from exc

        id_campus = image_data.get("id_campus")
        id_field = image_data.get("id_field")
        if id_campus != campus.id_campus:
            raise http_error(
                BOOKING_BAD_REQUEST,
                detail="Image campus id must match the campus being updated",
            )
        if id_field is not None:
            raise http_error(
                BOOKING_BAD_REQUEST,
                detail="Campus images cannot reference a field",
            )

        image_id = image_data.get("id_image")
        if image_id is not None:
            image = existing_images_by_id.get(image_id)
            if image is None:
                raise http_error(
                    BOOKING_NOT_FOUND,
                    detail=f"Image {image_id} not found for campus {campus.id_campus}",
                )
            incoming_ids.add(image_id)
            updated_fields = {
                key: value
                for key, value in image_data.items()
                if key != "id_image"
            }
            for attr, value in updated_fields.items():
                if attr == "image_url" and value is not None:
                    try:
                        validate_https_image_url(str(value))
                    except ValueError as exc:
                        raise http_error(BOOKING_BAD_REQUEST, detail=str(exc)) from exc
                setattr(image, attr, value)
        else:
            new_image_data = {
                key: value for key, value in image_data.items() if key != "id_image"
            }
            campus.images.append(Image(**new_image_data))

    for image in list(campus_images):
        if image.id_image is not None and image.id_image not in incoming_ids:
            campus.images.remove(image)
            image_repository.delete_image(db, image)
