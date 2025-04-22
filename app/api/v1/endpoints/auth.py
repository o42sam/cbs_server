from fastapi import APIRouter, Depends, HTTPException
from app.services.auth import AuthService
from app.api.v1.schemas.auth import Token
from typing import Optional

router = APIRouter()

async def get_auth_service():
    return AuthService()

@router.post("/login", response_model=Token)
async def login(email: str, password: str, two_fa_code: Optional[str] = None, auth_service: AuthService = Depends(get_auth_service)):
    try:
        return await auth_service.login(email, password, two_fa_code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))