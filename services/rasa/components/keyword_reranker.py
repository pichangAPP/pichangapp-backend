"""Post-NLU intent re-ranker based on deterministic keyword rules.

This component runs AFTER DIETClassifier and BEFORE FallbackClassifier. It
promotes a target intent to the top of the ranking when the message contains
a strong pivot keyword (e.g. "reservaciones" -> request_user_reservations),
without lowering the global fallback threshold. The component only overrides
DIETClassifier when:

- The current top confidence is below `min_top_confidence` (DIET is unsure).
- The target intent already exists in the ranking.
- The distance between the current top confidence and the target confidence is
  at most `max_gap` (we never promote a completely unlikely intent).

When promoted, the target confidence is lifted to `promoted_confidence` (which
must be >= the FallbackClassifier threshold so the bot actually accepts it).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional, Text

from rasa.engine.graph import ExecutionContext, GraphComponent
from rasa.engine.recipes.default_recipe import DefaultV1Recipe
from rasa.engine.storage.resource import Resource
from rasa.engine.storage.storage import ModelStorage
from rasa.shared.nlu.constants import (
    INTENT,
    INTENT_NAME_KEY,
    INTENT_RANKING_KEY,
    PREDICTED_CONFIDENCE_KEY,
)
from rasa.shared.nlu.training_data.message import Message

LOGGER = logging.getLogger(__name__)


def _strip_accents(value: Text) -> Text:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


@DefaultV1Recipe.register(
    [DefaultV1Recipe.ComponentType.INTENT_CLASSIFIER],
    is_trainable=False,
)
class KeywordIntentReranker(GraphComponent):
    """Deterministic keyword-based reranker for DIETClassifier output."""

    @classmethod
    def create(
        cls,
        config: Dict[Text, Any],
        model_storage: ModelStorage,
        resource: Resource,
        execution_context: ExecutionContext,
    ) -> "KeywordIntentReranker":
        return cls(config)

    def __init__(self, config: Dict[Text, Any]) -> None:
        defaults = self.get_default_config()
        merged: Dict[Text, Any] = {**defaults, **(config or {})}
        self.max_gap: float = float(merged.get("max_gap", 0.25))
        self.min_top_confidence: float = float(merged.get("min_top_confidence", 0.9))
        self.promoted_confidence: float = float(
            merged.get("promoted_confidence", 0.85)
        )
        self.ignore_accents: bool = bool(merged.get("ignore_accents", True))
        raw_rules = merged.get("rules") or []
        self._compiled: List[tuple] = []
        for rule in raw_rules:
            pattern = rule.get("pattern") if isinstance(rule, dict) else None
            target = rule.get("intent") if isinstance(rule, dict) else None
            if not pattern or not target:
                continue
            try:
                self._compiled.append(
                    (
                        re.compile(pattern, re.IGNORECASE | re.UNICODE),
                        str(target),
                    )
                )
            except re.error as exc:
                LOGGER.warning(
                    "[KeywordIntentReranker] invalid regex '%s' for intent '%s': %s",
                    pattern,
                    target,
                    exc,
                )

    @staticmethod
    def get_default_config() -> Dict[Text, Any]:
        return {
            "max_gap": 0.25,
            "min_top_confidence": 0.9,
            "promoted_confidence": 0.85,
            "ignore_accents": True,
            "rules": [],
        }

    @classmethod
    def required_packages(cls) -> List[Text]:
        return []

    def process(self, messages: List[Message]) -> List[Message]:
        for message in messages:
            try:
                self._rerank(message)
            except Exception as exc:
                LOGGER.warning(
                    "[KeywordIntentReranker] skipping message due to error: %s",
                    exc,
                )
        return messages

    def _rerank(self, message: Message) -> None:
        if not self._compiled:
            return

        text_raw = (message.get("text") or "").strip()
        if not text_raw:
            return

        candidates = [text_raw, text_raw.lower()]
        if self.ignore_accents:
            candidates.append(_strip_accents(text_raw).lower())
        haystacks = tuple(dict.fromkeys(candidates))

        ranking: List[Dict[Text, Any]] = list(
            message.get(INTENT_RANKING_KEY) or []
        )
        top = message.get(INTENT) or {}
        top_name = top.get(INTENT_NAME_KEY)
        top_conf = float(top.get(PREDICTED_CONFIDENCE_KEY, 0.0) or 0.0)
        if top_conf >= self.min_top_confidence:
            return

        for regex, target_intent in self._compiled:
            if not any(regex.search(haystack) for haystack in haystacks):
                continue
            if top_name == target_intent:
                return

            match: Optional[Dict[Text, Any]] = next(
                (
                    entry
                    for entry in ranking
                    if entry.get(INTENT_NAME_KEY) == target_intent
                ),
                None,
            )
            if match is None:
                continue
            current_target_conf = float(
                match.get(PREDICTED_CONFIDENCE_KEY, 0.0) or 0.0
            )
            if top_conf - current_target_conf > self.max_gap:
                continue

            new_conf = max(current_target_conf, self.promoted_confidence)
            match[PREDICTED_CONFIDENCE_KEY] = new_conf
            ranking.sort(
                key=lambda entry: entry.get(PREDICTED_CONFIDENCE_KEY, 0.0) or 0.0,
                reverse=True,
            )
            message.set(INTENT_RANKING_KEY, ranking, add_to_output=True)
            message.set(
                INTENT,
                {INTENT_NAME_KEY: target_intent, PREDICTED_CONFIDENCE_KEY: new_conf},
                add_to_output=True,
            )
            LOGGER.info(
                "[KeywordIntentReranker] promoted '%s' over '%s' for text='%s' "
                "(top_conf=%.3f target_conf=%.3f new_conf=%.3f)",
                target_intent,
                top_name,
                text_raw,
                top_conf,
                current_target_conf,
                new_conf,
            )
            return
