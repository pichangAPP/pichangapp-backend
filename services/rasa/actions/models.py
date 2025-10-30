"""Domain models shared across Rasa actions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FieldRecommendation:
    """Represents a field recommendation result."""

    id_field: int
    field_name: str
    sport_name: str
    campus_name: str
    district: str
    address: str
    surface: str
    capacity: int
    price_per_hour: float
    open_time: str
    close_time: str


__all__ = ["FieldRecommendation"]
