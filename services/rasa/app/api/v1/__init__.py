"""Version 1 API routes for the chatbot service."""

from fastapi import APIRouter

from .chat_routes import router as chat_router

router = APIRouter()
router.include_router(chat_router, prefix="/chatbot", tags=["chatbot"])

__all__ = ["router"]
