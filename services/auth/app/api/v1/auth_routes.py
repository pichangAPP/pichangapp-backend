from fastapi import APIRouter

router = APIRouter()

@router.get("/test")
def test_auth():
    return {"message": "Auth service working!"}
