from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterable, Optional

from rasa_sdk.types import DomainDict

from ...infrastructure.security import (
    TokenDecodeError,
    decode_access_token,
    extract_role_from_claims,
)

LOGGER = logging.getLogger(__name__)


def coerce_metadata(value: Any) -> Dict[str, Any]:
    """Convierte metadata en un diccionario seguro."""
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        text = value.strip()
        if text:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                LOGGER.debug("[Metadata] Unable to decode metadata string as JSON")
            else:
                if isinstance(parsed, dict):
                    return dict(parsed)
    return {}


def coerce_user_identifier(value: Any) -> Optional[int]:
    """Normaliza el identificador de usuario a entero cuando sea posible."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if stripped.isdigit():
            return int(stripped)
        for separator in (":", "-", "_", "|"):
            candidate = stripped.split(separator)[-1]
            if candidate.isdigit():
                return int(candidate)
        try:
            return int(stripped)
        except ValueError:
            return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_role_from_metadata(metadata: Dict[str, Any]) -> Optional[str]:
    """Resuelve el rol del usuario desde metadata y sus variantes."""
    raw_role = metadata.get("user_role") or metadata.get("role")
    if isinstance(raw_role, str):
        lowered = raw_role.strip().lower()
        if lowered in {"admin", "player"}:
            return lowered
        try:
            numeric = int(lowered)
            if numeric == 2:
                return "admin"
            if numeric == 1:
                return "player"
        except ValueError:
            pass
    elif raw_role is not None:
        try:
            numeric = int(raw_role)
            if numeric == 2:
                return "admin"
            if numeric == 1:
                return "player"
        except (TypeError, ValueError):
            pass

    role_id = metadata.get("id_role")
    if role_id is not None:
        try:
            numeric = int(role_id)
            if numeric == 2:
                return "admin"
            if numeric == 1:
                return "player"
        except (TypeError, ValueError):
            return None

    return metadata.get("default_role") if metadata.get("default_role") in {"admin", "player"} else None


def extract_token_from_metadata(metadata: Dict[str, Any]) -> Optional[str]:
    """Busca el token de autenticacion dentro de la metadata."""
    candidates = [
        metadata.get("token"),
        metadata.get("access_token"),
        metadata.get("auth_token"),
        metadata.get("authorization"),
        metadata.get("Authorization"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate

    headers = metadata.get("headers")
    if isinstance(headers, dict):
        header_token = headers.get("Authorization") or headers.get("authorization")
        if isinstance(header_token, str) and header_token.strip():
            return header_token

    nested_candidates = [metadata.get("customData"), metadata.get("user"), metadata.get("auth")]
    for container in nested_candidates:
        if isinstance(container, dict):
            nested_token = (
                container.get("token")
                or container.get("access_token")
                or container.get("Authorization")
                or container.get("authorization")
            )
            if isinstance(nested_token, str) and nested_token.strip():
                return nested_token

    return None


def enrich_metadata_with_token(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Decodifica el token y enriquece metadata con claims relevantes."""
    token = extract_token_from_metadata(metadata)
    if not token:
        return metadata

    try:
        claims = decode_access_token(token)
    except TokenDecodeError:
        LOGGER.warning("[Token] Unable to decode token from metadata", exc_info=True)
        return metadata

    metadata.setdefault("token_claims", claims)

    user_identifier = claims.get("id_user") or claims.get("sub")
    if user_identifier is not None and "id_user" not in metadata:
        try:
            metadata["id_user"] = int(user_identifier)
        except (TypeError, ValueError):
            metadata["id_user"] = user_identifier

    if "user_id" not in metadata and "id_user" in metadata:
        metadata["user_id"] = metadata["id_user"]

    if "id_role" not in metadata and "id_role" in claims:
        metadata["id_role"] = claims["id_role"]

    role_name = extract_role_from_claims(claims)
    if role_name:
        metadata.setdefault("role", role_name)
        metadata.setdefault("user_role", role_name)
        metadata.setdefault("default_role", role_name)

    return metadata


def slot_already_planned(events: Iterable[Any], slot_name: str) -> bool:
    """Verifica si un SlotSet ya fue planeado en los eventos."""
    for event in events:
        if hasattr(event, "key") and getattr(event, "key") == slot_name:
            return True
        if hasattr(event, "name") and getattr(event, "name") == slot_name:
            event_type = getattr(event, "event", None)
            if event_type == "slot":
                return True
        if isinstance(event, dict):
            event_type = event.get("event") or event.get("type")
            slot_key = event.get("name") or event.get("slot")
            if event_type == "slot" and slot_key == slot_name:
                return True
    return False


def slot_defined(slot_name: str, domain: DomainDict) -> bool:
    """Retorna True si el slot existe en el dominio cargado."""
    if domain is None:
        return False

    slots: Any = None

    if hasattr(domain, "as_dict") and callable(getattr(domain, "as_dict")):
        try:
            domain_dict = domain.as_dict()
        except Exception:  # pragma: no cover - defensive
            domain_dict = None
        else:
            slots = domain_dict.get("slots")
            if isinstance(slots, dict):
                return slot_name in slots
            if isinstance(slots, list):
                for slot in slots:
                    if isinstance(slot, dict) and slot.get("name") == slot_name:
                        return True

    if isinstance(domain, dict):
        slots = domain.get("slots")
    else:  # pragma: no cover - fallback for Domain objects
        try:
            slots = getattr(domain, "slots")
        except AttributeError:
            slots = None
        if slots is None:
            try:
                slot_names = getattr(domain, "slot_names")
            except AttributeError:
                slot_names = None
            else:
                if callable(slot_names):
                    try:
                        names = slot_names()
                    except TypeError:
                        names = list(slot_names)
                else:
                    names = slot_names
                if isinstance(names, Iterable) and slot_name in names:
                    return True

    if isinstance(slots, dict):
        return slot_name in slots
    if isinstance(slots, list):
        for slot in slots:
            if isinstance(slot, dict):
                name = slot.get("name") or slot.get("slot_name")
            else:
                name = getattr(slot, "name", None)
            if name == slot_name:
                return True

    return False
