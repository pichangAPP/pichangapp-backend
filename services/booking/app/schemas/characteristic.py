from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class CharacteristicBase(BaseModel):
    lights: bool
    toilets: bool
    parking: bool
    jerseys: bool
    store: bool
    coffee: bool
    restaurant: bool
    arbitration: bool
    emergency_kit: bool
    streaming: bool
    rest_area: bool
    scoreboard: bool
    spectator_area: bool
    wifi: bool
    tournaments: bool
    coporative_event: bool
    recreational_act: bool


class CharacteristicCreate(CharacteristicBase):
    pass


class CharacteristicUpdate(BaseModel):
    lights: Optional[bool] = None
    toilets: Optional[bool] = None
    parking: Optional[bool] = None
    jerseys: Optional[bool] = None
    store: Optional[bool] = None
    coffee: Optional[bool] = None
    restaurant: Optional[bool] = None
    arbitration: Optional[bool] = None
    emergency_kit: Optional[bool] = None
    streaming: Optional[bool] = None
    rest_area: Optional[bool] = None
    scoreboard: Optional[bool] = None
    spectator_area: Optional[bool] = None
    wifi: Optional[bool] = None
    tournaments: Optional[bool] = None
    coporative_event: Optional[bool] = None
    recreational_act: Optional[bool] = None


class CharacteristicResponse(CharacteristicBase):
    model_config = ConfigDict(from_attributes=True)

    id_characteristic: int
