from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, TYPE_CHECKING

from rasa_sdk.types import DomainDict

from ...infrastructure.config import get_settings
from ...infrastructure.security import (
    TokenDecodeError,
    decode_access_token,
    extract_role_from_claims,
)

if TYPE_CHECKING:
    from rasa_sdk import Tracker

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

    metadata["token_claims"] = claims

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


_SENSITIVE_METADATA_KEYS = frozenset(
    {
        "token",
        "access_token",
        "auth_token",
        "refresh_token",
        "authorization",
        "id_token",
        "password",
        "secret",
    }
)


def _is_sensitive_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    lowered = key.lower()
    if lowered in _SENSITIVE_METADATA_KEYS:
        return True
    return lowered.endswith("_token") or lowered.endswith("_secret")


def redact_metadata_for_logging(metadata: Any) -> Any:
    """Copia superficial/profunda de metadata apta para logs (sin JWT ni cabeceras de auth)."""
    if not isinstance(metadata, dict):
        return metadata
    redacted = copy.deepcopy(metadata)
    _redact_mapping_for_logging(redacted)
    return redacted


def _redact_mapping_for_logging(obj: Dict[str, Any]) -> None:
    for key in list(obj.keys()):
        if _is_sensitive_key(key) or key == "token_claims":
            obj[key] = "***"
            continue
        val = obj[key]
        if isinstance(val, dict):
            _redact_mapping_for_logging(val)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    _redact_mapping_for_logging(item)


def redact_slot_values_for_logging(slots: Any) -> Any:
    """Enmascara slots que puedan contener secretos (p. ej. user_token legado)."""
    if not isinstance(slots, dict):
        return slots
    out = copy.deepcopy(slots)
    if out.get("user_token"):
        out["user_token"] = "***"
    return out


@dataclass(frozen=True)
class SecuredActor:
    """Usuario efectivo tras aplicar JWT y política de enforce."""

    user_id: Optional[int]
    role: str
    token_valid: bool
    admin_authorized: bool
    enriched_metadata: Dict[str, Any]


def _claims_from_enriched_metadata(metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    claims = metadata.get("token_claims")
    return claims if isinstance(claims, dict) else None


def resolve_secured_actor(
    tracker: "Tracker",
    raw_metadata: Any,
    *,
    for_admin_action: bool = False,
) -> SecuredActor:
    """Resuelve rol e id_user para acciones; admin requiere JWT válido si enforce está activo."""
    metadata = enrich_metadata_with_token(dict(coerce_metadata(raw_metadata)))
    enforce = get_settings().ENFORCE_JWT_FOR_ADMIN_ACTIONS
    claims = _claims_from_enriched_metadata(metadata)
    token_valid = claims is not None

    if token_valid and claims is not None:
        role_name = extract_role_from_claims(claims) or "player"
        if role_name not in ("admin", "player"):
            role_name = "player"
        uid = coerce_user_identifier(claims.get("id_user") or claims.get("sub"))
        return SecuredActor(
            user_id=uid,
            role=role_name,
            token_valid=True,
            admin_authorized=role_name == "admin",
            enriched_metadata=metadata,
        )

    if enforce and for_admin_action:
        return SecuredActor(
            user_id=None,
            role="player",
            token_valid=False,
            admin_authorized=False,
            enriched_metadata=metadata,
        )

    role_raw = tracker.get_slot("user_role") or normalize_role_from_metadata(metadata) or "player"
    role_name = role_raw.lower() if isinstance(role_raw, str) else "player"
    if role_name not in ("admin", "player"):
        role_name = "player"
    uid = coerce_user_identifier(
        metadata.get("id_user") or metadata.get("user_id") or tracker.get_slot("user_id")
    )
    return SecuredActor(
        user_id=uid,
        role=role_name,
        token_valid=False,
        admin_authorized=role_name == "admin",
        enriched_metadata=metadata,
    )


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
            pass
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
