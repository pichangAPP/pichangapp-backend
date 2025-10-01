from fastapi import FastAPI

from app.api.v1 import router as v1_router

app = FastAPI(title="Booking Service")

app.include_router(
    v1_router,
    prefix="/api/pichangapp/v1/booking",
)
