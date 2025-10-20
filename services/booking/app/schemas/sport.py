from __future__ import annotations

from pydantic import BaseModel, ConfigDict


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