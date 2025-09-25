from fastapi import FastAPI

from app.api.v1 import auth_routes, user_routes

app = FastAPI(title="Auth Service")

# incluir rutas
app.include_router(auth_routes.router, prefix="/api/pichangapp/v1/auth", tags=["auth"])
app.include_router(user_routes.router, prefix="/api/pichangapp/v1/users", tags=["users"])

@app.get("/health")
def health_check():
    return {"status": "ok"}
