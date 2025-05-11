# app/services/auth.py
from app.schemas.user import User
from app.core.security import get_password_hash, verify_password, create_access_token, generate_2fa_secret, verify_2fa_code
from typing import Optional
from app.core.config import settings # Import settings
from datetime import timedelta
import random
# Assuming DatabaseUnavailableError is in app.exceptions.base or app.exceptions.database
from app.exceptions.base import DatabaseUnavailableError # Or the correct path
from app.exceptions.user import UserAlreadyExistsError, InvalidCredentialsError # For specific exceptions

class AuthService:
    SECURITY_QUESTIONS = [
        "What was your childhood nickname?", "What is your favorite book?",
        "What was the name of your first pet?", "What is your mother's maiden name?",
        "What was your favorite childhood game?", "What is your favorite movie?",
        "What was the name of your elementary school?", "What is your favorite food?",
        "What was your first job?", "What is your favorite vacation spot?"
    ]

    async def register(self, user_data: dict):
        if not settings.MONGODB_AVAILABLE:
            raise DatabaseUnavailableError(db_name="MongoDB", operation="user registration")

        # Check if email exists
        existing_user = await User.find_one(User.email == user_data["email"])
        if existing_user:
            raise UserAlreadyExistsError(email=user_data["email"]) # More specific error

        user_data["password"] = get_password_hash(user_data["password"])
        
        # Handle security questions if provided in user_data
        # The original code assumed f"answer_{i}" which might come from a form.
        # Adapting to a more generic user_data["security_answers"] if available, or keeping original.
        # For this example, let's assume the original structure for security questions.
        provided_answers = [user_data.pop(f"answer_{i}", None) for i in range(1, 3)] # Pop up to 2 answers
        
        questions = random.sample(self.SECURITY_QUESTIONS, 2)
        user_data["security_questions"] = []
        for i, q in enumerate(questions):
            answer = provided_answers[i] # Get corresponding answer
            if answer is None:
                # Handle case where not enough answers were provided for the sampled questions
                # This might mean raising an error or skipping the question.
                # For now, let's assume this structure means answers are expected to match questions.
                # If `answer_i` keys are not strictly tied to `questions` sample, this logic needs review.
                # raise ValueError(f"Missing answer for security question: {q}")
                # Or, if security questions are optional:
                continue # Skip if no answer for this question slot
            user_data["security_questions"].append(
                 {"question": q, "answer": get_password_hash(answer)}
            )

        user = User(**user_data)
        await user.insert()
        return user

    async def login(self, email: str, password: str, two_fa_code: Optional[str] = None):
        if not settings.MONGODB_AVAILABLE:
            raise DatabaseUnavailableError(db_name="MongoDB", operation="user login")

        user = await User.find_one(User.email == email)
        if not user or not verify_password(password, user.password):
            raise InvalidCredentialsError() # More specific error

        if settings.MODE == "strict":
            if not user.two_fa_secret: # Assuming two_fa_secret is on the User model
                 raise ValueError("2FA is required but not configured for this user.")
            if not two_fa_code:
                raise ValueError("2FA code required in strict mode.")
            if not verify_2fa_code(user.two_fa_secret, two_fa_code):
                raise ValueError("Invalid 2FA code.")
        
        token_data = {"sub": str(user.id)}
        if user.is_admin: # Add admin claim if user is admin
            token_data["is_admin"] = True

        token = create_access_token(token_data, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        return {"access_token": token, "token_type": "bearer", "user_id": str(user.id), "is_admin": user.is_admin}