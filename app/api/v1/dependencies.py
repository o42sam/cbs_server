from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.core.security import decode_access_token
from app.schemas.user import User
from app.core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await User.get(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

async def get_current_admin(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough privileges")
    return current_user

async def enforce_strict_mode(current_user: User = Depends(get_current_user)):
    if settings.MODE == "strict" and not (current_user.is_phone_number_verified and current_user.security_questions):
        raise HTTPException(status_code=403, detail="Strict mode requirements not met")
    return current_user