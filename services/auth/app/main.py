from fastapi import FastAPI

from app.api.v1 import auth_routes, user_routes
from app.api.v1.internal_routes import router as internal_router
from app.core.error_handlers import register_exception_handlers
from app.core.kafka import ERROR_LOGS_TOPIC, KafkaConsumerWorker, kafka_enabled

app = FastAPI(title="Auth Service")

register_exception_handlers(app)

# incluir rutas
app.include_router(auth_routes.router, prefix="/api/pichangapp/v1/auth", tags=["auth"])
app.include_router(user_routes.router, prefix="/api/pichangapp/v1/users", tags=["users"])
app.include_router(internal_router, prefix="/api/pichangapp/v1")

kafka_worker: KafkaConsumerWorker | None = None
if kafka_enabled():
    kafka_worker = KafkaConsumerWorker([ERROR_LOGS_TOPIC])


@app.on_event("startup")
def _start_kafka_worker() -> None:
    if kafka_worker is not None:
        kafka_worker.start()


@app.on_event("shutdown")
def _stop_kafka_worker() -> None:
    if kafka_worker is not None:
        kafka_worker.stop()

