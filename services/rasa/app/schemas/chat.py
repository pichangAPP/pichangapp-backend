"""Request and response models for the chatbot API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Mensaje a enviar al bot")
    conversation_id: Optional[str] = Field(
        default=None,
        description="Identificador opcional para mantener la conversación.",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Metadatos adicionales a adjuntar en el mensaje.",
    )


class ChatbotMessage(BaseModel):
    recipient_id: Optional[str] = None
    text: Optional[str] = None
    image: Optional[str] = None
    custom: Optional[Dict[str, Any]] = None


class ChatMessageResponse(BaseModel):
    conversation_id: str
    messages: List[ChatbotMessage]


class ChatHistoryMessage(BaseModel):
    message: str
    bot_response: str
    response_type: str
    sender_type: str
    timestamp: datetime
    intent_confidence: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class ChatHistorySession(BaseModel):
    session_id: int
    theme: str
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    messages: List[ChatHistoryMessage]


class ChatHistoryResponse(BaseModel):
    user_id: int
    sessions: List[ChatHistorySession]


__all__ = [
    "ChatMessageRequest",
    "ChatMessageResponse",
    "ChatbotMessage",
    "ChatHistoryMessage",
    "ChatHistorySession",
    "ChatHistoryResponse",
]
