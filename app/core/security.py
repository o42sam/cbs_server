from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import JWTError, jwt
from app.core.config import settings
import pyotp
from typing import Optional

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_access_token(token: str):
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None

def generate_2fa_secret():
    return pyotp.random_base32()

def verify_2fa_code(secret: str, code: str):
    totp = pyotp.TOTP(secret)
    return totp.verify(code)