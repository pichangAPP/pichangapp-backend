from __future__ import annotations

from app.models import Campus, Characteristic, Field, Image
from app.schemas import CampusCreate


def build_campus_entity(campus_in: CampusCreate) -> Campus:
    """Construye la entidad Campus con caracteristicas, campos e imagenes.

    Usado en: CampusService.create_campus y BusinessService.create_business.
    """
    campus_data = campus_in.model_dump(exclude={"characteristic", "fields", "images"})
    campus = Campus(**campus_data)
    characteristic = Characteristic(**campus_in.characteristic.model_dump())
    campus.characteristic = characteristic

    for field_in in campus_in.fields:
        campus.fields.append(Field(**field_in.model_dump()))
    for image_in in campus_in.images:
        campus.images.append(Image(**image_in.model_dump()))
    return campus
