# app/api/v1/schemas/transaction.py
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from beanie import PydanticObjectId

# Use PydanticObjectId from beanie for consistency if it's the standard in the project
# from beanie import PydanticObjectId # Assuming this is what was used before
# For clarity, I'll use a distinct name if there's a clash, or ensure consistent import
# PydanticObjectId = PydanticObjectIdType # or from beanie import PydanticObjectId


class TransactionBase(BaseModel):
    amount: float
    currency: str = Field(..., min_length=3, max_length=3)
    transaction_type: str
    status: str
    description: Optional[str] = None
    source_details: Optional[Dict[str, Any]] = None
    destination_details: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

class TransactionCreate(TransactionBase):
    source_account_id: Optional[PydanticObjectId] = None # For DB link
    destination_account_id: Optional[PydanticObjectId] = None # For DB link
    
    # For creating via API, user might provide identifiers rather than PydanticObjectIds directly
    # This can be handled in the endpoint/service, or accept IDs and resolve them.
    # For simplicity in this schema, we assume IDs are resolved before this model is populated for DB.
    # Or, add separate fields for account_number/id string inputs if needed.

    @field_validator('amount')
    @classmethod
    def validate_amount_positive(cls, v):
        if v <= 0:
            raise ValueError('Transaction amount must be positive')
        return v

    @field_validator('transaction_type')
    @classmethod
    def validate_transaction_type(cls, v):
        allowed_types = ["transfer", "deposit", "withdrawal", "payment", "fee", "manual_entry"]
        val = v.lower().strip()
        if val not in allowed_types:
            raise ValueError(f"Transaction type must be one of: {', '.join(allowed_types)}")
        return val

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed_statuses = ["pending", "processing", "completed", "failed", "cancelled", "pending_external", "reversed"]
        val = v.lower().strip()
        if val not in allowed_statuses:
            raise ValueError(f"Status must be one of: {', '.join(allowed_statuses)}")
        return val
    
    @field_validator('currency')
    @classmethod
    def validate_currency_code(cls, v: str) -> str:
        return v.upper()

class TransactionRead(TransactionBase):
    id: PydanticObjectId = Field(..., alias='_id')
    source_account_id: Optional[PydanticObjectId] = None
    destination_account_id: Optional[PydanticObjectId] = None
    created: datetime
    updated: datetime

    class Config:
        from_attributes = True
        populate_by_name = True
        json_encoders = {
            PydanticObjectId: str,
            datetime: lambda dt: dt.isoformat(),
        }

class TransactionUpdate(BaseModel):
    description: Optional[str] = None
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator('status', check_fields=False)
    @classmethod
    def validate_status_update(cls, v):
        if v is None: return v
        allowed_statuses = ["pending", "processing", "completed", "failed", "cancelled", "pending_external", "reversed"]
        val = v.lower().strip()
        if val not in allowed_statuses:
            raise ValueError(f"Status must be one of: {', '.join(allowed_statuses)}")
        return val

class FundTransferRequest(BaseModel):
    source_account_identifier: str = Field(..., description="Account number or ID of the source account")
    amount: float = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3, description="Currency code (e.g., NGN, USD)")
    description: Optional[str] = None

    destination_account_identifier: Optional[str] = Field(None, description="Account number or ID of the internal destination account")
    destination_details: Optional[Dict[str, Any]] = Field(None, description="Details for external transfer (must include 'bank_name' and 'account_number')")
    metadata: Optional[Dict[str, Any]] = None

    @field_validator('currency')
    @classmethod
    def validate_currency_code(cls, v: str) -> str:
        return v.upper()

    @model_validator(mode='after')
    def check_destination(cls, values):
        # Using .get() to avoid AttributeError if keys are missing after potential Pydantic v1 to v2 migration syntax differences.
        # In Pydantic v2, accessing attributes directly (values.destination_account_identifier) is standard.
        # For robustness with potential missing keys if not provided:
        dest_id = getattr(values, 'destination_account_identifier', None)
        dest_details = getattr(values, 'destination_details', None)

        if not dest_id and not dest_details:
            raise ValueError("Either 'destination_account_identifier' (for internal transfer) or 'destination_details' (for external transfer) must be provided.")
        if dest_id and dest_details:
            raise ValueError("Provide either 'destination_account_identifier' or 'destination_details', not both.")
        
        if dest_details:
            if not isinstance(dest_details.get("bank_name"), str) or not dest_details.get("bank_name").strip():
                raise ValueError("For external transfers, 'bank_name' must be a non-empty string in destination_details.")
            if not isinstance(dest_details.get("account_number"), str) or not dest_details.get("account_number").strip():
                raise ValueError("For external transfers, 'account_number' must be a non-empty string in destination_details.")
            # Example of further arbitrary field validation if needed:
            # beneficiary_name = dest_details.get("beneficiary_name")
            # if not beneficiary_name or not isinstance(beneficiary_name, str):
            # raise ValueError("Beneficiary name is required for this type of external transfer.")
        return values

class FundTransferResponse(BaseModel):
    message: str
    transaction_id: PydanticObjectId
    status: str # e.g., "completed" for internal, "pending_external" for external
    timestamp: datetime
    amount: float
    currency: str
    source_account_id: PydanticObjectId # Resolved ID of the source account
    destination_account_id: Optional[PydanticObjectId] = None # Resolved ID if internal
    destination_details: Optional[Dict[str, Any]] = None # Echo back details if external

    class Config:
        from_attributes = True # Required if mapping from ORM models directly
        json_encoders = {
            PydanticObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }