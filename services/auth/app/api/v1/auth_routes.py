from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.dependencies import get_db
from app.models.user import User

router = APIRouter()

@router.get("/db-test")
def db_test(db: Session = Depends(get_db)):
    user_count = db.query(User).count()
    return {"users_in_db": user_count}
