"""Resolución tolerante a mayúsculas, acentos y espacios para distritos y deportes."""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, Optional

from .text_utils import normalize_plain_text

try:
    from rapidfuzz import fuzz, process
except ImportError:  # pragma: no cover - optional at import time
    fuzz = None  # type: ignore[assignment]
    process = None  # type: ignore[assignment]

# Distritos oficiales (alineado con lookup `location` en nlu.yml).
LIMA_DISTRICTS_CANONICAL: Tuple[str, ...] = (
    "Ancón",
    "Ate",
    "Barranco",
    "Breña",
    "Carabayllo",
    "Cieneguilla",
    "Comas",
    "Chaclacayo",
    "Chorrillos",
    "El Agustino",
    "Independencia",
    "Jesús María",
    "La Molina",
    "La Victoria",
    "Lima",
    "Lince",
    "Los Olivos",
    "Lurigancho",
    "Lurín",
    "Magdalena del Mar",
    "Miraflores",
    "Pachacámac",
    "Pucusana",
    "Pueblo Libre",
    "Puente Piedra",
    "Punta Hermosa",
    "Punta Negra",
    "Rímac",
    "San Bartolo",
    "San Borja",
    "San Isidro",
    "San Juan de Lurigancho",
    "San Juan de Miraflores",
    "San Luis",
    "San Martín de Porres",
    "San Miguel",
    "Santa Anita",
    "Santa María del Mar",
    "Santa Rosa",
    "Santiago de Surco",
    "Surquillo",
    "Villa El Salvador",
    "Villa María del Triunfo",
)

# Nombres cortos o fusionados frecuentes -> nombre canónico del distrito.
LOCATION_EXTRA_ALIASES: Dict[str, str] = {
    "surco": "Santiago de Surco",
    "santiagodesurco": "Santiago de Surco",
    "santiagodesurcolima": "Santiago de Surco",
    "magdalena": "Magdalena del Mar",
    "magdalenadelmar": "Magdalena del Mar",
    "sanisidro": "San Isidro",
    "sanisdro": "San Isidro",
    "ves": "Villa El Salvador",
    "villaelsalvador": "Villa El Salvador",
    "villaelsalvad": "Villa El Salvador",
    "villaelsal": "Villa El Salvador",
    "villaelsalv": "Villa El Salvador",
    "villaelsalva": "Villa El Salvador",
    "villaelsalvdor": "Villa El Salvador",
    "villaelsalvadorlima": "Villa El Salvador",
    "vmt": "Villa María del Triunfo",
    "villamariadeltriunfo": "Villa María del Triunfo",
    "villamtriunfo": "Villa María del Triunfo",
    "sjl": "San Juan de Lurigancho",
    "sanjuandelurigancho": "San Juan de Lurigancho",
    "sanjuandeluriganch": "San Juan de Lurigancho",
    "sjm": "San Juan de Miraflores",
    "sanjuandemiraflores": "San Juan de Miraflores",
    "smp": "San Martín de Porres",
    "sanmartindeporres": "San Martín de Porres",
    "sanmartindepores": "San Martín de Porres",
    "jesusmaria": "Jesús María",
    "jesusmaría": "Jesús María",
    "lamolina": "La Molina",
    "lavictoria": "La Victoria",
    "losolivos": "Los Olivos",
    "puentepiedra": "Puente Piedra",
    "puntanegra": "Punta Negra",
    "puntahermosa": "Punta Hermosa",
    "santamariadelmar": "Santa María del Mar",
    "santarosa": "Santa Rosa",
    "sanborja": "San Borja",
    "sanmiguel": "San Miguel",
    "santaanita": "Santa Anita",
    "pachacamac": "Pachacámac",
    "pueblolibre": "Pueblo Libre",
    "puente piedra": "Puente Piedra",
    "rimac": "Rímac",
    "ancon": "Ancón",
    "atevitarte": "Ate",
    "brena": "Breña",
    "lurin": "Lurín",
    "cieneguilla": "Cieneguilla",
    "chaclacayo": "Chaclacayo",
    "carabayllo": "Carabayllo",
    "elagustino": "El Agustino",
    "cercadodelima": "Lima",
    "cercadodelimalima": "Lima",
}

CANONICAL_SPORTS: Tuple[str, ...] = ("football", "basketball", "volleyball", "tennis", "padel")

SPORT_EXTRA_ALIASES: Dict[str, str] = {
    "futbol": "football",
    "fútbol": "football",
    "futbol7": "football",
    "futbol5": "football",
    "fútbol7": "football",
    "fútbol5": "football",
    "fulbito": "football",
    "futsal": "football",
    "soccer": "football",
    "pelota": "football",
    "pichanga": "football",
    "basket": "basketball",
    "basquet": "basketball",
    "básquet": "basketball",
    "baloncesto": "basketball",
    "basquetbol": "basketball",
    "voley": "volleyball",
    "vóley": "volleyball",
    "voleibol": "volleyball",
    "voleyball": "volleyball",
    "volley": "volleyball",
    "tenis": "tennis",
    "pádel": "padel",
}

_FUZZ_LOCATION_THRESHOLD = 86
_FUZZ_SPORT_THRESHOLD = 88


def _ascii_fold(value: str) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFD", value.strip())
    stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return stripped.lower()


def _compact_alnum(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _ascii_fold(value))


def _single_spaced(value: str) -> str:
    return re.sub(r"\s+", " ", _ascii_fold(value)).strip()


def _build_location_alias_map() -> Dict[str, str]:
    alias: Dict[str, str] = dict(LOCATION_EXTRA_ALIASES)
    for canonical in LIMA_DISTRICTS_CANONICAL:
        alias[_single_spaced(canonical)] = canonical
        alias[_compact_alnum(canonical)] = canonical
    return alias


_LOCATION_ALIAS_MAP: Dict[str, str] = _build_location_alias_map()


def resolve_lima_district(raw: Optional[str]) -> Optional[str]:
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None

    spaced = _single_spaced(text)
    compact = _compact_alnum(text)
    if compact in _LOCATION_ALIAS_MAP:
        return _LOCATION_ALIAS_MAP[compact]
    if spaced in _LOCATION_ALIAS_MAP:
        return _LOCATION_ALIAS_MAP[spaced]

    if len(spaced) >= 5 and process is not None and fuzz is not None:
        best = process.extractOne(
            spaced,
            LIMA_DISTRICTS_CANONICAL,
            scorer=fuzz.WRatio,
        )
        if best:
            match, score, _ = best
            if score >= _FUZZ_LOCATION_THRESHOLD:
                return str(match)

    return text


def resolve_sport_canonical(raw: Optional[str]) -> Optional[str]:
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None

    spaced = _single_spaced(text)
    compact = _compact_alnum(text)
    if compact in SPORT_EXTRA_ALIASES:
        return SPORT_EXTRA_ALIASES[compact]
    if spaced in SPORT_EXTRA_ALIASES:
        return SPORT_EXTRA_ALIASES[spaced]

    if len(spaced) >= 4 and process is not None and fuzz is not None:
        best = process.extractOne(
            spaced,
            CANONICAL_SPORTS,
            scorer=fuzz.WRatio,
        )
        if best:
            match, score, _ = best
            if score >= _FUZZ_SPORT_THRESHOLD:
                return str(match)

    lowered = normalize_plain_text(text)
    if any(k in lowered for k in ("futbol", "fulbito", "futsal", "soccer")):
        return "football"
    if any(k in lowered for k in ("basket", "basquet", "baloncesto")):
        return "basketball"
    if any(k in lowered for k in ("voley", "voleibol", "volley")):
        return "volleyball"
    if "tenis" in lowered or "tennis" in lowered:
        return "tennis"
    if "padel" in lowered:
        return "padel"

    return text


__all__ = [
    "CANONICAL_SPORTS",
    "LIMA_DISTRICTS_CANONICAL",
    "resolve_lima_district",
    "resolve_sport_canonical",
]
