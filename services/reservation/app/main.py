"""Entry point for the Reservation FastAPI application."""

from fastapi import FastAPI

from app.api.v1 import rent_routes, schedule_routes
from app.core.config import settings
from app.core.database import Base, engine
from app.core.error_handlers import register_exception_handlers

# Ensure database tables exist when the application starts (for development purposes).
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.PROJECT_NAME)

register_exception_handlers(app)

# Register routers
app.include_router(
    schedule_routes.router,
    prefix="/api/pichangapp/v1/reservation",
)
app.include_router(
    rent_routes.router,
    prefix="/api/pichangapp/v1/reservation",
)
