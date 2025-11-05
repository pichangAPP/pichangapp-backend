"""SQLAlchemy ORM models for the analytics schema used by Rasa actions."""

from __future__ import annotations

from datetime import datetime, time
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Time, BigInteger, Numeric, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarative class for the analytics models."""


class Chatbot(Base):
    """Represents a chat session in analytics.chatbot."""

    __tablename__ = "chatbot"
    __table_args__ = {"schema": "analytics"}

    id_chatbot: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    theme: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    id_user: Mapped[int] = mapped_column(BigInteger, nullable=False)

    logs: Mapped[list["ChatbotLog"]] = relationship(
        "ChatbotLog", back_populates="chatbot", cascade="all, delete-orphan"
    )


class Intent(Base):
    """Represents an intent in analytics.intents."""

    __tablename__ = "intents"
    __table_args__ = {"schema": "analytics"}

    id_intent: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intent_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    example_phrases: Mapped[str] = mapped_column(Text, nullable=True)
    response_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence_avg: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    total_detected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    false_positives: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_model: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_detected: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    logs: Mapped[list["ChatbotLog"]] = relationship("ChatbotLog", back_populates="intent")


class RecommendationLog(Base):
    """Represents analytics.recomendation_log entries."""

    __tablename__ = "recomendation_log"
    __table_args__ = {"schema": "analytics"}

    id_recommendation_log: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_time_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    suggested_time_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    id_field: Mapped[int] = mapped_column(Integer, ForeignKey("booking.field.id_field"), nullable=False)
    id_user: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    chatbot_logs: Mapped[list["ChatbotLog"]] = relationship(
        "ChatbotLog", back_populates="recommendation"
    )


class ChatbotLog(Base):
    """Represents analytics.chatbot_log entries."""

    __tablename__ = "chatbot_log"
    __table_args__ = {"schema": "analytics"}

    id_chatbot_log: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    response_type: Mapped[str] = mapped_column(String(50), nullable=False)
    bot_response: Mapped[str] = mapped_column(Text, nullable=False, default="")
    intent_detected: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sender_type: Mapped[str] = mapped_column(String(30), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    id_chatbot: Mapped[int] = mapped_column(Integer, ForeignKey("analytics.chatbot.id_chatbot"))
    id_intent: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("analytics.intents.id_intent"), nullable=True
    )
    id_recommendation_log: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("analytics.recomendation_log.id_recommendation_log"), nullable=True
    )
    id_user: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    intent_confidence: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column("metadata", Text, nullable=True)


    chatbot: Mapped[Chatbot] = relationship("Chatbot", back_populates="logs")
    intent: Mapped[Optional[Intent]] = relationship("Intent", back_populates="logs")
    recommendation: Mapped[Optional[RecommendationLog]] = relationship(
        "RecommendationLog", back_populates="chatbot_logs"
    )


class Feedback(Base):
    """Represents analytics.feedback entries."""

    __tablename__ = "feedback"
    __table_args__ = {"schema": "analytics"}

    id_feedback: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    id_user: Mapped[int] = mapped_column(BigInteger, nullable=False)
    id_rent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class Field(Base):
    """Represents booking.field entries."""

    __tablename__ = "field"
    __table_args__ = {"schema": "booking"}

    id_field: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    field_name: Mapped[str] = mapped_column(String(255), nullable=False)
    surface: Mapped[str] = mapped_column(String(100), nullable=True)
    capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    price_per_hour: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    open_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    close_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    id_sport: Mapped[int] = mapped_column(Integer, ForeignKey("booking.sports.id_sport"), nullable=False)
    id_campus: Mapped[int] = mapped_column(Integer, ForeignKey("booking.campus.id_campus"), nullable=False)

    sport: Mapped["Sport"] = relationship("Sport", back_populates="fields")
    campus: Mapped["Campus"] = relationship("Campus", back_populates="fields")
    recommendations: Mapped[list[RecommendationLog]] = relationship(
        "RecommendationLog", backref="field"
    )


class Sport(Base):
    """Represents booking.sports entries."""

    __tablename__ = "sports"
    __table_args__ = {"schema": "booking"}

    id_sport: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sport_name: Mapped[str] = mapped_column(String(100), nullable=False)

    fields: Mapped[list[Field]] = relationship("Field", back_populates="sport")


class Campus(Base):
    """Represents booking.campus entries."""

    __tablename__ = "campus"
    __table_args__ = {"schema": "booking"}

    id_campus: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    district: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    fields: Mapped[list[Field]] = relationship("Field", back_populates="campus")


__all__ = [
    "Base",
    "Campus",
    "Chatbot",
    "ChatbotLog",
    "Feedback",
    "Field",
    "Intent",
    "RecommendationLog",
    "Sport",
]
