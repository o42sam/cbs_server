
from beanie import Document, Link, PydanticObjectId
from pydantic import Field
from typing import Optional
from datetime import datetime

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .account import Account

class Transaction(Document):
    amount: float
    currency: str
    type: str
    status: str
    description: Optional[str] = None
    created: datetime = Field(default_factory=datetime.utcnow)
    updated: datetime = Field(default_factory=datetime.utcnow)


    source_account_id: Optional[Link["Account"]] = None
    destination_account_id: Optional[Link["Account"]] = None








    class Settings:
        name = "transactions"
        indexes = [
            [("source_account_id", 1), ("created", -1)],
            [("destination_account_id", 1), ("created", -1)],
            [("created", -1)],
        ]

    @Field.validator('amount')
    @classmethod
    def validate_amount_positive(cls, v):
        if v <= 0:
            raise ValueError('Transaction amount must be positive')
        return v