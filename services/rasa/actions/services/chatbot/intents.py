from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Sequence

from ...infrastructure.database import get_session
from ...repositories.analytics.analytics_repository import IntentRepository
from .retry import RetryExecutor


class IntentAnalyticsOperations:
    """Operaciones de analitica de intents."""

    def __init__(
        self,
        *,
        executor: RetryExecutor,
        logger: logging.Logger,
        source_model: str,
    ) -> None:
        self._executor = executor
        self._logger = logger
        self._source_model = source_model

    def ensure_intent(
        self,
        *,
        intent_name: str,
        example_phrases: Sequence[str],
        response_template: str,
        confidence: Optional[float],
        detected: bool,
        false_positive: bool,
        source_model: Optional[str] = None,
    ) -> int:
        timestamp = datetime.now(timezone.utc)
        cleaned_examples = {
            phrase.strip()
            for phrase in example_phrases
            if phrase and phrase.strip()
        }

        self._logger.info(
            "[ChatbotAnalyticsService] ensure_intent name=%s detected=%s false_positive=%s",
            intent_name,
            detected,
            false_positive,
        )

        def _fetch_existing() -> Optional[Dict[str, Any]]:
            with get_session() as session:
                repository = IntentRepository(session)
                return repository.fetch_by_name(intent_name)

        existing = self._executor.execute(_fetch_existing, action="fetch_intent")

        normalized_confidence = None
        if confidence is not None:
            normalized_confidence = round(float(confidence), 4)

        if existing:
            existing_examples = existing.get("example_phrases") or ""
            example_set = {
                line.strip()
                for line in existing_examples.splitlines()
                if line.strip()
            }
            example_set.update(cleaned_examples)
            examples_text = "\n".join(sorted(example_set))

            previous_total = int(existing.get("total_detected") or 0)
            previous_confidence = float(existing.get("confidence_avg") or 0.0)
            total_detected = previous_total

            if detected:
                total_detected += 1

            confidence_avg = previous_confidence
            if detected and normalized_confidence is not None:
                if previous_total <= 0:
                    confidence_avg = normalized_confidence
                else:
                    confidence_avg = round(
                        (
                            (previous_confidence * previous_total)
                            + normalized_confidence
                        )
                        / (previous_total + 1),
                        4,
                    )

            false_positives_count = int(existing.get("false_positives") or 0)
            if false_positive:
                false_positives_count += 1

            def _update_operation() -> None:
                with get_session() as session:
                    repository = IntentRepository(session)
                    repository.update(
                        intent_id=int(existing["id_intent"]),
                        example_phrases=examples_text,
                        response_template=response_template,
                        confidence_avg=confidence_avg,
                        total_detected=total_detected,
                        false_positives=false_positives_count,
                        source_model=source_model or self._source_model,
                        last_detected=timestamp if detected else None,
                        updated_at=timestamp,
                    )

            self._executor.execute(_update_operation, action="update_intent")
            self._logger.debug(
                "[ChatbotAnalyticsService] updated intent id=%s total_detected=%s",
                existing["id_intent"],
                total_detected,
            )
            return int(existing["id_intent"])

        examples_text = "\n".join(sorted(cleaned_examples))

        def _create_operation() -> int:
            with get_session() as session:
                repository = IntentRepository(session)
                return repository.create(
                    intent_name=intent_name,
                    example_phrases=examples_text,
                    response_template=response_template,
                    confidence_avg=normalized_confidence or 0.0,
                    total_detected=1 if detected else 0,
                    false_positives=1 if false_positive else 0,
                    source_model=source_model or self._source_model,
                    last_detected=timestamp if detected else None,
                    created_at=timestamp,
                    updated_at=timestamp,
                )

        intent_id = self._executor.execute(_create_operation, action="create_intent")
        self._logger.debug(
            "[ChatbotAnalyticsService] created intent id=%s name=%s",
            intent_id,
            intent_name,
        )
        return intent_id
