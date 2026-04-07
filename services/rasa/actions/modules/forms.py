from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Text

from rasa_sdk import FormValidationAction, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict


_METRIC_TYPE_REGEX: List[tuple[str, str]] = [
    (r"\b(comparativo|comparacion|comparar|ranking|rank)\b", "comparativo"),
    (r"\b(tendencia|tendencias|evolucion)\b", "tendencia"),
    (r"\b(clientes?|usuarios?\s+frecuentes?|top\s+clientes?)\b", "clientes"),
    (r"\b(canchas?|campos?|fields?|espacios?\s+deportivos?)\b", "canchas"),
    (r"\b(ocupacion|ocu|disponibilidad)\b", "ocupacion"),
    (r"\b(trafico|traf|flujo)\b", "trafico"),
    (r"\b(ingresos?|ingreso|revenue|income|ventas?|facturacion)\b", "ingresos"),
]

_METRIC_PERIOD_REGEX: List[tuple[str, str]] = [
    (r"\b(hoy|dia|today|ahorita)\b", "hoy"),
    (r"\b(esta\s+semana|semana|semanal|week|sem)\b", "semana"),
    (r"\b(este\s+mes|mes|mensual|month)\b", "mes"),
]


def _normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    lowered = value.strip().lower()
    normalized = unicodedata.normalize("NFD", lowered)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _extract_metric_type(value: Any) -> Optional[str]:
    normalized = _normalize_text(value)
    if not normalized:
        return None
    for pattern, canonical in _METRIC_TYPE_REGEX:
        if re.search(pattern, normalized):
            return canonical
    return None


def _extract_metric_period(value: Any) -> Optional[str]:
    normalized = _normalize_text(value)
    if not normalized:
        return None
    for pattern, canonical in _METRIC_PERIOD_REGEX:
        if re.search(pattern, normalized):
            return canonical
    return None


def _is_generic_metrics_request(value: Any) -> bool:
    normalized = _normalize_text(value)
    if not normalized:
        return False
    return bool(
        re.search(r"\b(metrica|metricas|indicador|indicadores|reporte|reportes)\b", normalized)
    )


class ValidateFieldRecommendationForm(FormValidationAction):
    """Validate the slots collected by the field recommendation form."""

    def name(self) -> str:
        return "validate_field_recommendation_form"

    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        base_slots: List[Text] = ["location", "sport", "time", "date"]
        if tracker.active_loop_name != "field_recommendation_form":
            return base_slots

        provided = [
            slot
            for slot in base_slots
            if tracker.get_slot(slot) not in (None, "", [], {})
        ]
        return base_slots if not provided else []

    async def validate_location(
        self,
        slot_value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        normalized = slot_value.strip() if isinstance(slot_value, str) else slot_value
        return {
            "location": normalized,
            "preferred_location": normalized,
        }

    async def validate_time(
        self,
        slot_value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        normalized = slot_value.strip() if isinstance(slot_value, str) else slot_value
        return {
            "time": normalized,
            "preferred_start_time": normalized,
        }

    async def validate_sport(
        self,
        slot_value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return {"sport": slot_value}

    async def validate_time(
        self,
        slot_value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return {"time": slot_value}

    async def validate_date(
        self,
        slot_value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return {"date": slot_value}


class ValidateAdminMetricsForm(FormValidationAction):
    """Validate the slots collected by the admin metrics form."""

    def name(self) -> str:
        return "validate_admin_metrics_form"

    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        base_slots: List[Text] = ["admin_metric_type", "admin_metric_period"]
        if tracker.active_loop_name != "admin_metrics_form":
            return base_slots

        required = [
            slot
            for slot in base_slots
            if tracker.get_slot(slot) in (None, "", [], {})
        ]

        latest_message = tracker.latest_message or {}
        latest_text = latest_message.get("text") or ""
        latest_type = _extract_metric_type(latest_text)
        latest_period = _extract_metric_period(latest_text)
        current_type = tracker.get_slot("admin_metric_type")
        current_period = tracker.get_slot("admin_metric_period")

        if latest_type and latest_type != current_type and "admin_metric_type" not in required:
            required.insert(0, "admin_metric_type")
        if latest_period and latest_period != current_period and "admin_metric_period" not in required:
            required.append("admin_metric_period")

        if (
            _is_generic_metrics_request(latest_text)
            and latest_type is None
            and "admin_metric_type" not in required
        ):
            required.insert(0, "admin_metric_type")

        return required

    async def validate_admin_metric_type(
        self,
        slot_value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        metric_type = _extract_metric_type(slot_value)
        updates: Dict[Text, Any] = {"admin_metric_type": metric_type}
        metric_period = _extract_metric_period(slot_value)
        if metric_period is not None:
            updates["admin_metric_period"] = metric_period
        return updates

    async def validate_admin_metric_period(
        self,
        slot_value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        metric_period = _extract_metric_period(slot_value)
        updates: Dict[Text, Any] = {"admin_metric_period": metric_period}
        metric_type = _extract_metric_type(slot_value)
        if metric_type is not None:
            updates["admin_metric_type"] = metric_type
        return updates


__all__ = ["ValidateFieldRecommendationForm", "ValidateAdminMetricsForm"]
