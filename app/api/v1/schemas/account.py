# app/api/v1/schemas/account.py

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from beanie import PydanticObjectId # Ensure this is the correct PydanticObjectId being used
from datetime import datetime, date
from app.schemas.account import Currency as CurrencyDB # Assuming CurrencyDB is the DB model from app.schemas.account

# PydanticObjectId = PydanticObjectId # from beanie

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
    # user_id: Optional[PydanticObjectId] = None # user_id is derived from current_user, not taken from request body
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
    
    @field_validator('currency_code')
    @classmethod
    def validate_code_length(cls, v):
        if len(v) != 3:
            raise ValueError('Currency code must be 3 letters (e.g., NGN, USD)')
        return v.upper()

class AccountLimitUpdate(BaseModel):
    balance_limit: Optional[float] = Field(None, ge=0)
    daily_debit_limit: Optional[float] = Field(None, ge=0)

    @field_validator('*', mode='before') # Pydantic v1 syntax, consider `model_validator` for v2
    @classmethod
    def check_at_least_one_value(cls, values):
        if isinstance(values, dict) and not any(values.values()): # Ensure it's a dict from Pydantic
             raise ValueError("At least one limit (balance_limit or daily_debit_limit) must be provided for update.")
        # If it's Pydantic v2 and this is a field validator, it receives a single value.
        # For a model validator:
        # from pydantic import model_validator
        # @model_validator(mode='before')
        # def check_at_least_one_value(cls, data):
        #     if not any(data.values()):
        #        raise ValueError("At least one limit must be provided.")
        #     return data
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

# REMOVED TransferRequest - it's now FundTransferRequest in app/api/v1/schemas/transaction.py
# class TransferRequest(BaseModel):
# source_identifier: str = Field(..., description="Account number or ID of the source account")
# destination_identifier: str = Field(..., description="Account number or ID of the destination account")
# amount: float = Field(..., gt=0)


class UserOwner(BaseModel):
    id: PydanticObjectId
    email: str
    full_name: str

    class Config:
        from_attributes = True
        # populate_by_name = True # Deprecated in Pydantic v2, use alias_generators or field aliases
        json_encoders = {PydanticObjectId: str}


class AccountRead(BaseModel):
    id: PydanticObjectId = Field(..., alias='_id')
    user: UserOwner
    account_number: str
    type: str
    currency: CurrencyDB # This should be the Pydantic model for Currency, not the DB class directly if they differ
    balance: float
    account_status: dict # Ideally, this should be a Pydantic model like AccountStatus in app.schemas.account
    balance_limit: Optional[float]
    daily_debit_limit: Optional[float]
    daily_debit_total: float
    last_debit_date: Optional[date]
    created: datetime
    updated: datetime

    class Config:
        from_attributes = True
        populate_by_name = True # For alias '_id'
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

# REMOVED TransferResponse - it's now FundTransferResponse in app/api/v1/schemas/transaction.py
# class TransferResponse(BaseModel):
# message: str = "Transfer successful"
# transaction_id: PydanticObjectId
# source_account_id: PydanticObjectId
# destination_account_id: PydanticObjectId
# amount: float
# currency: str
# timestamp: datetime
# class Config:
# json_encoders = {
# PydanticObjectId: str,
# datetime: lambda dt: dt.isoformat()
# }