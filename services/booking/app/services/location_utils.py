from __future__ import annotations

from math import atan2, cos, radians, sin, sqrt


def haversine_distance(
    latitude_1: float,
    longitude_1: float,
    latitude_2: float,
    longitude_2: float,
) -> float:
    """Return the haversine distance in kilometers between two coordinates."""
    radius_earth_km = 6371.0

    lat1_rad = radians(latitude_1)
    lon1_rad = radians(longitude_1)
    lat2_rad = radians(latitude_2)
    lon2_rad = radians(longitude_2)

    diff_lat = lat2_rad - lat1_rad
    diff_lon = lon2_rad - lon1_rad

    a = sin(diff_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(diff_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return radius_earth_km * c
