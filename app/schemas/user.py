
from beanie import Document, Link
from pydantic import EmailStr, Field, BaseModel, field_validator
from typing import List, Optional
from datetime import datetime


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .account import Account

class UserStatus(BaseModel):
    status: str = "unrestricted"
    description: str = ""

class User(Document):
    first_name: str
    last_name: str
    other_names: Optional[str] = None
    email: EmailStr
    image: Optional[str] = None
    gender: Optional[str] = None
    location: Optional[str] = None
    is_email_verified: bool = False
    is_phone_number_verified: bool = False
    password: str
    date_of_birth: Optional[datetime] = None
    phone_number: Optional[str] = None
    created: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    user_status: UserStatus = Field(default_factory=UserStatus)

    accounts: List[Link["Account"]] = []
    tier: int = 1
    trusted_origins: List[str] = []
    is_omnipotent: bool = False
    referrals: List[str] = []
    referred_by: Optional[str] = None
    security_questions: List[dict] = []
    is_admin: bool = False

    @field_validator('tier')
    @classmethod
    def validate_tier(cls, v):
        if v not in [1, 2, 3]:
            raise ValueError('Tier must be 1, 2, or 3')
        return v

    class Settings:
        name = "users"

        indexes = [
            [("email", 1)],
        ]