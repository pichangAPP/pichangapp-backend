from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(register_data: RegisterRequest, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    return auth_service.register_user(register_data)


@router.post("/login", response_model=TokenResponse)
def login_user(login_data: LoginRequest, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    access_token, user = auth_service.login_user(login_data)
    return {"access_token": access_token, "token_type": "bearer", "user": user}


@router.get("/db-test")
def db_test(db: Session = Depends(get_db)):
    from app.models.user import User

    user_count = db.query(User).count()
    return {"users_in_db": user_count}
