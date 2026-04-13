"""Use-case orchestration for recommendation fetching and logging."""

from __future__ import annotations

import logging
from datetime import datetime, time as time_of_day
from typing import Any, Dict, List, Optional, Set, Tuple

from ...models import FieldRecommendation
from ...services.chatbot_service import DatabaseError, chatbot_service
from ...domain.chatbot.async_utils import run_in_thread
from ...domain.chatbot.recommendations import (
    describe_relaxations,
    serialize_filter_payload,
)

LOGGER = logging.getLogger(__name__)


async def persist_recommendation_logs(
    *,
    user_id: int,
    recommendations: List[FieldRecommendation],
    summaries: List[str],
    start_dt: datetime,
    end_dt: datetime,
) -> Tuple[Optional[int], List[int]]:
    stored_ids: List[int] = []
    primary_id: Optional[int] = None
    for idx, (rec, message_text) in enumerate(zip(recommendations, summaries)):
        status = "suggested" if idx == 0 else "suggested_alternative"
        try:
            rec_id = await run_in_thread(
                chatbot_service.create_recommendation_log,
                status=status,
                message=message_text,
                suggested_start=start_dt,
                suggested_end=end_dt,
                field_id=rec.id_field,
                user_id=user_id,
            )
        except DatabaseError:
            LOGGER.exception(
                "[ActionSubmitFieldRecommendationForm] database error creating recommendation log for field_id=%s",
                rec.id_field,
            )
            continue
        stored_ids.append(rec_id)
        if idx == 0:
            primary_id = rec_id
    return primary_id, stored_ids


async def fetch_recommendations_with_relaxation(
    *,
    sport: Optional[str],
    surface: Optional[str],
    location: Optional[str],
    min_price: Optional[float],
    max_price: Optional[float],
    target_time: Optional[time_of_day],
    prioritize_price: bool,
    prioritize_rating: bool,
    limit: int,
) -> Tuple[List[FieldRecommendation], Dict[str, Any], List[str], str, Set[str]]:
    requests = [
        ("exact_match", set()),
        ("relaxed_budget", {"budget"}),
        ("relaxed_time", {"budget", "time"}),
        ("relaxed_surface", {"budget", "time", "surface"}),
        ("location_focus", {"budget", "time", "surface", "sport"}),
        ("relaxed_location", {"budget", "time", "surface", "sport", "location"}),
        ("generic_popular", {"budget", "time", "surface", "sport", "location", "price_priority"}),
    ]
    sport_is_required = bool(sport and str(sport).strip())
    for label, drops in requests:
        if sport_is_required and "sport" in drops:
            continue
        params_sport = None if "sport" in drops else sport
        params_surface = None if "surface" in drops else surface
        params_location = None if "location" in drops else location
        params_min_price = None if "budget" in drops else min_price
        params_max_price = None if "budget" in drops else max_price
        params_time = None if "time" in drops else target_time
        params_prioritize_price = False if "price_priority" in drops else prioritize_price
        params_prioritize_rating = prioritize_rating
        recommendations: List[FieldRecommendation] = await run_in_thread(
            chatbot_service.fetch_field_recommendations,
            sport=params_sport,
            surface=params_surface,
            location=params_location,
            limit=limit,
            min_price=params_min_price,
            max_price=params_max_price,
            target_time=params_time,
            prioritize_price=params_prioritize_price,
            prioritize_rating=params_prioritize_rating,
        )
        if recommendations:
            applied_filters = serialize_filter_payload(
                sport=params_sport,
                surface=params_surface,
                location=params_location,
                min_price=params_min_price,
                max_price=params_max_price,
                target_time=params_time,
                prioritize_price=params_prioritize_price,
                prioritize_rating=params_prioritize_rating,
            )
            notes = describe_relaxations(
                drops,
                sport=sport,
                surface=surface,
                location=location,
                min_price=min_price,
                max_price=max_price,
                target_time=target_time,
            )
            return recommendations, applied_filters, notes, label, drops

    fallback_filters = serialize_filter_payload(
        sport=sport,
        surface=surface,
        location=location,
        min_price=min_price,
        max_price=max_price,
        target_time=target_time,
        prioritize_price=prioritize_price,
        prioritize_rating=prioritize_rating,
    )
    return [], fallback_filters, [], "no_results", set()
