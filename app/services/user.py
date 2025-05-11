# app/services/user.py
from typing import List, Optional, Dict, Any
from beanie import PydanticObjectId
# from beanie.operators import Or # Not used here
from datetime import datetime

from app.core.config import settings # Import settings
from app.schemas.user import User
from app.api.v1.schemas.user import UserUpdate # Assuming this is a Pydantic model for updates
from app.exceptions.user import UserNotFoundError, UserAlreadyExistsError
from app.core.security import get_password_hash
# Assuming DatabaseUnavailableError is in app.exceptions.base or app.exceptions.database
from app.exceptions.base import DatabaseUnavailableError # Or the correct path

class UserService:
    async def get_user_by_id(self, user_id: PydanticObjectId) -> User:
        if not settings.MONGODB_AVAILABLE:
            # print(f"WARNING: MongoDB not available. Cannot fetch user {user_id}.")
            # Depending on strictness, either return None or raise error. Raising is safer.
            raise DatabaseUnavailableError(db_name="MongoDB", operation=f"get user by ID {user_id}")
        
        user = await User.get(user_id)
        if not user:
            raise UserNotFoundError(identifier=str(user_id))
        return user

    async def get_user_by_email(self, email: str) -> Optional[User]:
        if not settings.MONGODB_AVAILABLE:
            # print(f"WARNING: MongoDB not available. Cannot fetch user by email {email}.")
            # For 'find_one' type operations, returning None might be acceptable.
            return None # Or raise DatabaseUnavailableError
        
        return await User.find_one(User.email == email)

    async def get_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        if not settings.MONGODB_AVAILABLE:
            # print("WARNING: MongoDB not available. Cannot fetch list of users.")
            return [] # Return empty list if DB is down for list operations
        
        return await User.find_all(skip=skip, limit=limit).to_list()

    async def create_user(self, user_data: Dict[str, Any]) -> User:
        if not settings.MONGODB_AVAILABLE:
            raise DatabaseUnavailableError(db_name="MongoDB", operation="create user")

        existing_user = await self.get_user_by_email(user_data["email"]) # Handles its own DB check
        if existing_user: # This check is only fully reliable if DB was up during get_user_by_email
            # If get_user_by_email returned None due to DB down, this might allow duplicate creation
            # when DB comes back up. A more robust check might be needed if get_user_by_email can return None for DB down.
            # However, if get_user_by_email raises error, then this is fine.
            # Let's assume get_user_by_email returns None if DB down for this path to proceed cautiously.
            # Re-checking: get_user_by_email returns None if DB down. This means if DB is down,
            # UserAlreadyExistsError might not be raised.
            # The `create_user` itself checks `settings.MONGODB_AVAILABLE` first, so it won't proceed to insert.
            raise UserAlreadyExistsError(email=user_data["email"])


        hashed_password = get_password_hash(user_data["password"])
        user_data_db = user_data.copy() # Work on a copy
        user_data_db["password"] = hashed_password

        hashed_security_questions = []
        for sq in user_data_db.get("security_questions", []):
            if "question" in sq and "answer" in sq and isinstance(sq["answer"], str):
                hashed_answer = get_password_hash(sq["answer"])
                hashed_security_questions.append({
                    "question": sq["question"],
                    "answer": hashed_answer
                })
        user_data_db["security_questions"] = hashed_security_questions
        
        # Default values
        user_data_db.setdefault("created", datetime.utcnow())
        user_data_db.setdefault("last_updated", datetime.utcnow())
        user_data_db.setdefault("is_email_verified", False)
        user_data_db.setdefault("is_phone_number_verified", False)
        user_data_db.setdefault("tier", 1) # Default tier if not provided
        user_data_db.setdefault("is_admin", False) # Default admin status


        # Filter to allowed fields in User model to prevent unexpected field errors
        allowed_fields = User.model_fields.keys()
        filtered_user_data = {k: v for k, v in user_data_db.items() if k in allowed_fields}
        
        user = User(**filtered_user_data)
        await user.insert()
        return user

    async def update_user(self, user_id: PydanticObjectId, update_data: UserUpdate) -> User:
        if not settings.MONGODB_AVAILABLE:
            raise DatabaseUnavailableError(db_name="MongoDB", operation=f"update user {user_id}")

        user = await self.get_user_by_id(user_id) # Handles its own DB check

        update_data_dict = update_data.model_dump(exclude_unset=True)

        if "password" in update_data_dict and update_data_dict["password"]:
            hashed_password = get_password_hash(update_data_dict["password"])
            user.password = hashed_password
            del update_data_dict["password"] # Remove from dict to prevent direct setattr

        for key, value in update_data_dict.items():
            if hasattr(user, key): # Make sure the attribute exists on the model
                setattr(user, key, value)

        user.last_updated = datetime.utcnow()
        await user.save()
        return user

    async def delete_user(self, user_id: PydanticObjectId) -> bool:
        if not settings.MONGODB_AVAILABLE:
            raise DatabaseUnavailableError(db_name="MongoDB", operation=f"delete user {user_id}")

        user = await self.get_user_by_id(user_id) # Handles its own DB check
        # Add any other pre-delete checks here (e.g., related accounts)
        
        delete_result = await user.delete()
        return delete_result.deleted_count > 0 if delete_result else False


def get_user_service() -> UserService: # This factory function remains the same
    return UserService()