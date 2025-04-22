from beanie import Document
from pydantic import Field
from datetime import datetime

class Card(Document):
    number: str
    expiry_date: datetime
    created: datetime = Field(default_factory=datetime.utcnow)
    cvv: str
    provider: str

    class Settings:
        name = "cards"