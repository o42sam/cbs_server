
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict
from beanie import PydanticObjectId
from datetime import datetime


class SecurityQuestionInput(BaseModel):
    question: str
    answer: str

class UserCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str = Field(min_length=8)
    phone_number: Optional[str] = None

    security_questions: List[SecurityQuestionInput] = Field(default=[], max_items=5)


class UserRead(BaseModel):
    id: PydanticObjectId = Field(..., alias='_id')
    first_name: str
    last_name: str
    other_names: Optional[str] = None
    email: EmailStr
    image: Optional[str] = None
    gender: Optional[str] = None
    location: Optional[str] = None
    is_email_verified: bool
    is_phone_number_verified: bool
    phone_number: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    created: datetime
    last_updated: datetime

    tier: int
    is_admin: bool

    class Config:
        from_attributes = True
        populate_by_name = True
        json_encoders = {PydanticObjectId: str}


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    other_names: Optional[str] = None
    image: Optional[str] = None
    gender: Optional[str] = None
    location: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)
    date_of_birth: Optional[datetime] = None
    phone_number: Optional[str] = None


