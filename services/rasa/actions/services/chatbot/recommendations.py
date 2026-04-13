from __future__ import annotations

import logging
from datetime import datetime, time as time_of_day
from typing import Any, Dict, List, Optional

from ...infrastructure.database import get_session
from ...models import FieldRecommendation
from ...repositories.analytics.analytics_repository import RecommendationRepository
from .retry import RetryExecutor


class RecommendationAnalyticsOperations:
    """Operaciones de recomendacion y consulta de canchas."""

    def __init__(self, *, executor: RetryExecutor, logger: logging.Logger) -> None:
        self._executor = executor
        self._logger = logger

    def create_recommendation_log(
        self,
        *,
        status: str,
        message: str,
        suggested_start: datetime,
        suggested_end: datetime,
        field_id: int,
        user_id: Optional[int],
    ) -> int:
        self._logger.info(
            "[ChatbotAnalyticsService] create_recommendation_log field_id=%s user_id=%s status=%s",
            field_id,
            user_id,
            status,
        )

        def _operation() -> int:
            with get_session() as session:
                repository = RecommendationRepository(session)
                return repository.create_log(
                    status=status,
                    message=message,
                    suggested_start=suggested_start,
                    suggested_end=suggested_end,
                    field_id=field_id,
                    user_id=user_id,
                )

        recommendation_id = self._executor.execute(
            _operation, action="create_recommendation_log"
        )
        self._logger.info(
            "[ChatbotAnalyticsService] recommendation log created id=%s",
            recommendation_id,
        )
        return recommendation_id

    def fetch_recommendation_history(self, session_id: int, limit: int) -> List[Dict[str, Any]]:
        self._logger.debug(
            "[ChatbotAnalyticsService] fetch_recommendation_history session_id=%s limit=%s",
            session_id,
            limit,
        )

        def _operation() -> List[Dict[str, Any]]:
            with get_session() as session:
                repository = RecommendationRepository(session)
                return repository.fetch_history(session_id, limit)

        return self._executor.execute(_operation, action="fetch_recommendation_history")

    def fetch_field_recommendations(
        self,
        *,
        sport: Optional[str],
        surface: Optional[str],
        location: Optional[str],
        limit: int,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        target_time: Optional[time_of_day] = None,
        prioritize_price: bool = False,
        prioritize_rating: bool = False,
    ) -> List[FieldRecommendation]:
        self._logger.debug(
            "[ChatbotAnalyticsService] fetch_field_recommendations sport=%s surface=%s location=%s limit=%s min_price=%s max_price=%s target_time=%s price_first=%s rating_first=%s",
            sport,
            surface,
            location,
            limit,
            min_price,
            max_price,
            target_time,
            prioritize_price,
            prioritize_rating,
        )

        def _operation() -> List[FieldRecommendation]:
            with get_session() as session:
                repository = RecommendationRepository(session)
                return repository.fetch_field_recommendations(
                    sport=sport,
                    surface=surface,
                    location=location,
                    limit=limit,
                    min_price=min_price,
                    max_price=max_price,
                    target_time=target_time,
                    prioritize_price=prioritize_price,
                    prioritize_rating=prioritize_rating,
                )

        return self._executor.execute(_operation, action="fetch_field_recommendations")
