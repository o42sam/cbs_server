
from beanie import Document, Link, PydanticObjectId
from pydantic import Field, BaseModel, field_validator, validator
from typing import List, Optional
from datetime import datetime, date


from .user import User
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .transaction import Transaction
    from .card import Card

class AccountStatus(BaseModel):
    status: str = "unrestricted"
    description: Optional[str] = ""

class Currency(BaseModel):
    name: str
    code: str
    symbol: str

    @field_validator('code')
    @classmethod
    def validate_code_length(cls, v):
        if len(v) != 3:
            raise ValueError('Currency code must be 3 letters (e.g., NGN, USD)')
        return v.upper()

class Account(Document):
    user_id: Link[User]
    account_number: str = Field(..., unique=True)
    type: str
    currency: Currency
    balance: float = Field(default=0.0)

    account_status: AccountStatus = Field(default_factory=AccountStatus)

    created: datetime = Field(default_factory=datetime.utcnow)
    updated: datetime = Field(default_factory=datetime.utcnow)
    balance_limit: Optional[float] = Field(default=1000000.0)
    daily_debit_limit: Optional[float] = Field(default=100000.0)


    daily_debit_total: float = Field(default=0.0)
    last_debit_date: Optional[date] = None

    class Settings:
        name = "accounts"
        indexes = [
            [("account_number", 1)],
            [("user_id", 1)],
        ]

    @field_validator('type')
    @classmethod
    def validate_account_type(cls, v):
        allowed_types = ["savings", "current"]
        if v.lower() not in allowed_types:
            raise ValueError(f"Account type must be one of: {', '.join(allowed_types)}")
        return v.lower()

    @field_validator('balance', 'daily_debit_total')
    @classmethod
    def validate_non_negative_float(cls, v):
        if v < 0:
            raise ValueError('Value cannot be negative')
        return v













    @validator('balance_limit', 'daily_debit_limit', pre=True, always=True)
    @classmethod
    def validate_limits_non_negative(cls, v):
         if v is not None and v < 0:
             raise ValueError('Limit values cannot be negative')
         return v


    def reset_daily_limit_if_needed(self):
        """Resets daily_debit_total if the last debit was on a previous day."""
        today = datetime.utcnow().date()
        if self.last_debit_date != today:
            self.daily_debit_total = 0.0
            self.last_debit_date = None