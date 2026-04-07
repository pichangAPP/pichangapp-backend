import time

from fastapi import FastAPI

from app.api.v1 import rent_routes, schedule_routes, status_catalog_routes
from app.core.config import settings
from app.core.database import ensure_rent_schedule_schema, ensure_reservation_functions
from app.core.error_handlers import register_exception_handlers

ensure_rent_schedule_schema()
ensure_reservation_functions()

app = FastAPI(title=settings.PROJECT_NAME)

register_exception_handlers(app)


@app.middleware("http")
async def _capture_request_start_time(request, call_next):
    request.state.start_time = time.perf_counter()
    return await call_next(request)

# Register routers
app.include_router(
    schedule_routes.router,
    prefix="/api/pichangapp/v1/reservation",
)
app.include_router(
    rent_routes.router,
    prefix="/api/pichangapp/v1/reservation",
)
app.include_router(
    status_catalog_routes.router,
    prefix="/api/pichangapp/v1/reservation",
)
