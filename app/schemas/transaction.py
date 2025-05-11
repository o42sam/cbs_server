# app/schemas/transaction.py
from beanie import Document, Link, PydanticObjectId
from pydantic import Field, field_validator
from typing import Optional, Dict, Any
from datetime import datetime

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .account import Account

class Transaction(Document):
    amount: float
    currency: str
    transaction_type: str  # e.g., "transfer", "deposit", "withdrawal", "payment", "fee", "manual_entry"
    status: str  # e.g., "pending", "completed", "failed", "cancelled", "processing", "pending_external"
    description: Optional[str] = None
    created: datetime = Field(default_factory=datetime.utcnow)
    updated: datetime = Field(default_factory=datetime.utcnow)

    source_account_id: Optional[Link["Account"]] = None  # For internal source
    destination_account_id: Optional[Link["Account"]] = None  # For internal destination

    # For external transfers or more detailed transactions
    source_details: Optional[Dict[str, Any]] = None # e.g. if source is external via a payment gateway
    destination_details: Optional[Dict[str, Any]] = None  # Stores bank name, account number, beneficiary, etc. for external transfers

    metadata: Optional[Dict[str, Any]] = None  # For any other arbitrary data like payment gateway reference, invoice number etc.

    class Settings:
        name = "transactions"
        indexes = [
            [("source_account_id", 1), ("created", -1)],
            [("destination_account_id", 1), ("created", -1)],
            [("transaction_type", 1), ("status", 1), ("created", -1)],
            [("created", -1)],
            [("currency", 1)],
        ]

    @field_validator('amount')
    @classmethod
    def validate_amount_positive_or_zero(cls, v): # Allow zero for some transaction types if necessary, but for most, positive.
        # For now, keeping the original "positive" validation from the prompt.
        # If zero amount transactions are possible (e.g. status updates as transactions), this might need adjustment.
        if v <= 0:
            raise ValueError('Transaction amount must be positive')
        return v

    @field_validator('transaction_type')
    @classmethod
    def validate_transaction_type(cls, v: str) -> str:
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