
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from beanie import PydanticObjectId
from datetime import datetime, date
from app.schemas.account import Currency as CurrencyDB



class CurrencyInput(BaseModel):
    """Simplified currency input, code is sufficient"""
    code: str

    @field_validator('code')
    @classmethod
    def validate_code_length(cls, v):
        if len(v) != 3:
            raise ValueError('Currency code must be 3 letters (e.g., NGN, USD)')
        return v.upper()

class AccountCreate(BaseModel):
    user_id: Optional[PydanticObjectId] = None
    type: str
    currency_code: str = "NGN"
    balance_limit: Optional[float] = Field(None, ge=0)
    daily_debit_limit: Optional[float] = Field(None, ge=0)

    @field_validator('type')
    @classmethod
    def validate_account_type(cls, v):
        allowed_types = ["savings", "current"]
        if v.lower() not in allowed_types:
            raise ValueError(f"Account type must be one of: {', '.join(allowed_types)}")
        return v.lower()

class AccountLimitUpdate(BaseModel):
    balance_limit: Optional[float] = Field(None, ge=0)
    daily_debit_limit: Optional[float] = Field(None, ge=0)


    @field_validator('*', mode='before')
    @classmethod
    def check_at_least_one_value(cls, values):
        if not any(values.values()):
            raise ValueError("At least one limit (balance_limit or daily_debit_limit) must be provided for update.")
        return values

class AccountStatusUpdate(BaseModel):
    status: str
    description: Optional[str] = None

    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        allowed_statuses = ["unrestricted", "restricted", "frozen"]
        if v.lower() not in allowed_statuses:
            raise ValueError(f"Status must be one of: {', '.join(allowed_statuses)}")
        return v.lower()

class TransferRequest(BaseModel):

    source_identifier: str = Field(..., description="Account number or ID of the source account")
    destination_identifier: str = Field(..., description="Account number or ID of the destination account")
    amount: float = Field(..., gt=0)




class UserOwner(BaseModel):
    id: PydanticObjectId
    email: str
    full_name: str

    class Config:
        from_attributes = True
        populate_by_name = True
        json_encoders = {PydanticObjectId: str}


class AccountRead(BaseModel):
    id: PydanticObjectId = Field(..., alias='_id')
    user: UserOwner
    account_number: str
    type: str
    currency: CurrencyDB
    balance: float
    account_status: dict
    balance_limit: Optional[float]
    daily_debit_limit: Optional[float]
    daily_debit_total: float
    last_debit_date: Optional[date]
    created: datetime
    updated: datetime

    class Config:
        from_attributes = True
        populate_by_name = True
        json_encoders = {
            PydanticObjectId: str,
            datetime: lambda dt: dt.isoformat(),
            date: lambda d: d.isoformat()
        }

class AccountStatusRead(BaseModel):
    account_number: str
    status: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class TransferResponse(BaseModel):
    message: str = "Transfer successful"
    transaction_id: PydanticObjectId
    source_account_id: PydanticObjectId
    destination_account_id: PydanticObjectId
    amount: float
    currency: str
    timestamp: datetime

    class Config:
        json_encoders = {
            PydanticObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }