from beanie import Document
from pydantic import EmailStr, Field
from datetime import datetime

class Admin(Document):
    email: EmailStr
    password: str
    created: datetime = Field(default_factory=datetime.utcnow)
    is_admin: bool = True

    class Settings:
        name = "admins"