from app.schemas.user import User
from app.core.security import get_password_hash, verify_password, create_access_token, generate_2fa_secret, verify_2fa_code
from typing import Optional
from app.core.config import settings
from datetime import timedelta
import random

class AuthService:
    SECURITY_QUESTIONS = [
        "What was your childhood nickname?", "What is your favorite book?",
        "What was the name of your first pet?", "What is your mother's maiden name?",
        "What was your favorite childhood game?", "What is your favorite movie?",
        "What was the name of your elementary school?", "What is your favorite food?",
        "What was your first job?", "What is your favorite vacation spot?"
    ]

    async def register(self, user_data: dict):
        if await User.find_one(User.email == user_data["email"]):
            raise ValueError("Email already registered")
        user_data["password"] = get_password_hash(user_data["password"])
        questions = random.sample(self.SECURITY_QUESTIONS, 2)
        user_data["security_questions"] = [
            {"question": q, "answer": get_password_hash(user_data.pop(f"answer_{i}"))}
            for i, q in enumerate(questions, 1)
        ]
        user = User(**user_data)
        await user.insert()

        return user

    async def login(self, email: str, password: str, two_fa_code: Optional[str] = None):
        user = await User.find_one(User.email == email)
        if not user or not verify_password(password, user.password):
            raise ValueError("Invalid credentials")
        if settings.MODE == "strict" and not two_fa_code:
            raise ValueError("2FA code required in strict mode")
        if settings.MODE == "strict" and not verify_2fa_code(user.two_fa_secret, two_fa_code):
            raise ValueError("Invalid 2FA code")
        token = create_access_token({"sub": str(user.id)}, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        return {"access_token": token, "token_type": "bearer"}