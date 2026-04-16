import time

from fastapi import FastAPI

from app.api.v1 import router as v1_router
from app.core.database import ensure_booking_functions
from app.core.error_handlers import register_exception_handlers
from app.core.schema_bootstrap import ensure_field_combination_tables

ensure_field_combination_tables()
ensure_booking_functions()

app = FastAPI(title="Booking Service")

register_exception_handlers(app)


@app.middleware("http")
async def _capture_request_start_time(request, call_next):
    request.state.start_time = time.perf_counter()
    return await call_next(request)

app.include_router(
    v1_router,
    prefix="/api/pichangapp/v1/booking",
)
