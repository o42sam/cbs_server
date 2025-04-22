from beanie import Document
from pydantic import Field
from typing import Optional
from datetime import datetime

class Notification(Document):
    target: str
    message: str
    created: datetime = Field(default_factory=datetime.utcnow)
    received: Optional[datetime]

    class Settings:
        name = "notifications"