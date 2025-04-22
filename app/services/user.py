
from typing import List, Optional, Dict, Any
from beanie import PydanticObjectId
from beanie.operators import Or
from datetime import datetime

from app.schemas.user import User
from app.api.v1.schemas.user import UserUpdate
from app.exceptions.user import UserNotFoundError, UserAlreadyExistsError
from app.core.security import get_password_hash

class UserService:
    async def get_user_by_id(self, user_id: PydanticObjectId) -> User:
        """Fetches a user by their MongoDB ObjectId."""
        user = await User.get(user_id)
        if not user:
            raise UserNotFoundError(identifier=str(user_id))
        return user

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Fetches a user by their email address."""

        return await User.find_one(User.email == email)

    async def get_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Fetches a list of users with pagination."""
        return await User.find_all(skip=skip, limit=limit).to_list()

    async def create_user(self, user_data: Dict[str, Any]) -> User:
        """
        Creates a new user record in the database.
        Handles password hashing and checks for existing email.
        Expects 'password' in user_data to be plain text.
        Expects 'security_questions' in user_data to be a list of dicts like [{"question": str, "answer": str (plain)}].
        """
        existing_user = await self.get_user_by_email(user_data["email"])
        if existing_user:
            raise UserAlreadyExistsError(email=user_data["email"])


        hashed_password = get_password_hash(user_data["password"])
        user_data["password"] = hashed_password


        hashed_security_questions = []
        for sq in user_data.get("security_questions", []):
            if "question" in sq and "answer" in sq:




                hashed_answer = get_password_hash(sq["answer"])
                hashed_security_questions.append({
                    "question": sq["question"],
                    "answer": hashed_answer
                })
        user_data["security_questions"] = hashed_security_questions



        user_data.setdefault("created", datetime.utcnow())
        user_data.setdefault("last_updated", datetime.utcnow())
        user_data.setdefault("is_email_verified", False)
        user_data.setdefault("is_phone_number_verified", False)




        allowed_fields = User.model_fields.keys()
        filtered_user_data = {k: v for k, v in user_data.items() if k in allowed_fields}

        user = User(**filtered_user_data)


        await user.insert()
        return user

    async def update_user(self, user_id: PydanticObjectId, update_data: UserUpdate) -> User:
        """Updates an existing user."""
        user = await self.get_user_by_id(user_id)

        update_data_dict = update_data.model_dump(exclude_unset=True)


        if "password" in update_data_dict and update_data_dict["password"]:
            hashed_password = get_password_hash(update_data_dict["password"])
            user.password = hashed_password
            del update_data_dict["password"]


        for key, value in update_data_dict.items():
            if hasattr(user, key):
                setattr(user, key, value)


        user.last_updated = datetime.utcnow()

        await user.save()
        return user

    async def delete_user(self, user_id: PydanticObjectId) -> bool:
        """Deletes a user by their ID."""
        user = await self.get_user_by_id(user_id)
        delete_result = await user.delete()
        return delete_result.deleted_count > 0



def get_user_service() -> UserService:
    """Dependency injector for UserService."""
    return UserService()