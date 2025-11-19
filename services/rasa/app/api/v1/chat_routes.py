"""Routing layer for the chatbot API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from actions.db_models import Chatbot, ChatbotLog
from app.clients.rasa_client import RasaClient
from app.core.config import settings
from app.core.database import DatabaseError, fetch_user_role, get_session
from app.core.security import (
    extract_role_from_claims,
    get_current_user,
)
from app.schemas.chat import (
    ChatHistoryMessage,
    ChatHistoryResponse,
    ChatHistorySession,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatbotMessage,
)

router = APIRouter()

_rasa_client = RasaClient(
    settings.RASA_SERVER_URL,
    timeout=settings.REQUEST_TIMEOUT,
)


def _resolve_user_id(payload: Dict[str, Any]) -> int:
    user_identifier = payload.get("sub") or payload.get("id")
    if user_identifier is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    try:
        return int(user_identifier)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido") from exc


def _normalize_role(payload: Dict[str, Any], user_id: int) -> str:
    role_value = payload.get("user_role") or payload.get("role")
    if role_value:
        if isinstance(role_value, str) and role_value.lower() == "admin":
            return "admin"
        try:
            if int(role_value) == 2:
                return "admin"
        except (TypeError, ValueError):
            pass

    role_id = payload.get("id_role")
    if role_id is not None:
        try:
            if int(role_id) == 2:
                return "admin"
        except (TypeError, ValueError):
            pass

    try:
        resolved_role = fetch_user_role(user_id)
    except DatabaseError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo obtener el rol del usuario",
        ) from exc

    if resolved_role == 2:
        return "admin"
    return "player"


def _coerce_message(payload: Dict[str, Any]) -> ChatbotMessage:
    if hasattr(ChatbotMessage, "model_validate"):
        return ChatbotMessage.model_validate(payload)  # type: ignore[attr-defined]
    return ChatbotMessage.parse_obj(payload)  # type: ignore[attr-defined]


@router.post("/messages", response_model=ChatMessageResponse, status_code=status.HTTP_200_OK)
async def send_message(
    request: ChatMessageRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> ChatMessageResponse:
    user_id = _resolve_user_id(current_user)

    user_role = _normalize_role(current_user, user_id)
    conversation_id = request.conversation_id or f"user-{user_id}"

    metadata: Dict[str, Any] = {}
    if request.metadata:
        metadata.update(request.metadata)
    metadata.update(
        {
            "user_id": user_id,
            "id_user": user_id,
            "user_role": user_role,
            "id_role": 2 if user_role == "admin" else 1,
            "token": current_user.get("token"),
        }
    )
    metadata.setdefault("model", settings.RASA_DEFAULT_SOURCE_MODEL)

    try:
        rasa_messages = await _rasa_client.send_message(
            conversation_id,
            request.message,
            metadata,
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=exc.response.text or "Error comunicándose con Rasa",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo contactar al servidor de Rasa",
        ) from exc

    messages = [_coerce_message(item) for item in rasa_messages]
    return ChatMessageResponse(conversation_id=conversation_id, messages=messages)


def _serialize_messages(logs: List[ChatbotLog]) -> List[ChatHistoryMessage]:
    sorted_logs = sorted(logs, key=lambda item: item.timestamp or datetime.min)
    serialized: List[ChatHistoryMessage] = []
    for log in sorted_logs:
        serialized.append(
            ChatHistoryMessage(
                message=log.message or "",
                bot_response=log.bot_response or "",
                response_type=log.response_type or "",
                sender_type=log.sender_type or "",
                timestamp=log.timestamp or datetime.min,
                intent_confidence=float(log.intent_confidence)
                if log.intent_confidence is not None
                else None,
                metadata=log.metadata_dict,
            )
        )
    return serialized


def _fetch_user_conversations(user_id: int) -> List[ChatHistorySession]:
    with get_session() as session:
        stmt = (
            select(Chatbot)
            .options(selectinload(Chatbot.logs))
            .where(Chatbot.id_user == user_id)
            .order_by(Chatbot.started_at.desc())
        )
        results = session.execute(stmt).scalars().all()

    history: List[ChatHistorySession] = []
    for chat in results:
        history.append(
            ChatHistorySession(
                session_id=chat.id_chatbot,
                theme=chat.theme,
                status=chat.status,
                started_at=chat.started_at,
                ended_at=chat.ended_at,
                messages=_serialize_messages(chat.logs or []),
            )
        )
    return history


@router.get(
    "/users/{user_id}/history",
    response_model=ChatHistoryResponse,
    status_code=status.HTTP_200_OK,
)
async def get_user_history(
    user_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> ChatHistoryResponse:
    requestor_id = _resolve_user_id(current_user)
    role_name = extract_role_from_claims(current_user)
    is_admin = role_name == "admin"
    if not is_admin and requestor_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para ver esta conversación",
        )

    try:
        sessions = _fetch_user_conversations(user_id)
    except DatabaseError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo obtener el historial del chat",
        ) from exc

    return ChatHistoryResponse(user_id=user_id, sessions=sessions)


__all__ = ["router"]
