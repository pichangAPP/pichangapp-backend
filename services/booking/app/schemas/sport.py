from __future__ import annotations

from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field as PydanticField,
    field_validator,
)


class SportBase(BaseModel):
    sport_name: str
    sport_type: str
    id_modality: int = PydanticField(..., gt=0)

    @field_validator("sport_name", "sport_type", mode="before")
    @classmethod
    def _strip_non_empty(cls, value: str) -> str:
        if value is None:
            raise ValueError("Value must not be null")
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value must not be empty")
        return stripped


class SportCreate(SportBase):
    pass


class SportUpdate(BaseModel):
    sport_name: Optional[str] = None
    sport_type: Optional[str] = None
    id_modality: Optional[int] = PydanticField(None, gt=0)

    @field_validator("sport_name", "sport_type", mode="before")
    @classmethod
    def _strip_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value must not be empty")
        return stripped


class ModalityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_modality: int
    modality_description: str
    players: int
    team: int


class SportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_sport: int
    sport_name: str
    sport_type: str
    modality: ModalityResponse