from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import Image


def list_images_by_campus(db: Session, campus_id: int) -> List[Image]:
    return (
        db.query(Image).filter(Image.id_campus == campus_id).order_by(Image.id_image).all()
    )


def get_image(db: Session, image_id: int) -> Optional[Image]:
    return db.query(Image).filter(Image.id_image == image_id).first()


def create_image(db: Session, image: Image) -> Image:
    db.add(image)
    db.flush()
    return image


def delete_image(db: Session, image: Image) -> None:
    db.delete(image)
