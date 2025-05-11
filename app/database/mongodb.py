# app/database/mongodb.py
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
# Ensure all your Beanie document models are imported
from app.schemas.user import User # Assuming User is a Beanie Document
from app.schemas.account import Account # Assuming Account is a Beanie Document
from app.schemas.transaction import Transaction # Assuming Transaction is a Beanie Document
from app.schemas.card import Card # Assuming Card is a Beanie Document
from app.schemas.notification import Notification # Assuming Notification is a Beanie Document
from app.schemas.admin import Admin # Assuming Admin is a Beanie Document
from typing import Dict, Optional

# Global MongoDB client instance
db_client: Optional[AsyncIOMotorClient] = None

# Placeholder for in-memory data if MongoDB is down
mock_mongo_store: Dict[str, list] = {
    "users": [],
    "accounts": [],
    "transactions": [],
    # Add other collections as needed
}

async def init_db():
    """Initializes the MongoDB connection or logs a warning if unavailable."""
    global db_client
    try:
        if not settings.MONGODB_URL:
            raise ValueError("MONGODB_URL is not set in the environment variables.")

        db_client = AsyncIOMotorClient(settings.MONGODB_URL)
        await db_client.admin.command('ping') # Verify connection

        # Initialize Beanie with all your document models
        # Ensure all models are correctly imported and are Beanie Documents
        document_models = [User, Account, Transaction, Card, Notification, Admin]
        await init_beanie(database=db_client.get_default_database(), document_models=document_models)

        settings.MONGODB_AVAILABLE = True
        print("INFO: Successfully connected to MongoDB and initialized Beanie.")

    except ValueError as e: # Specifically for MONGODB_URL not set
        print(f"CRITICAL: MongoDB configuration error: {e}")
        print("INFO: MongoDB features will be unavailable. Application will run with limited functionality.")
        db_client = None # Ensure db_client is None
        settings.MONGODB_AVAILABLE = False
    except Exception as e:
        print(f"WARNING: Could not connect to MongoDB at {settings.MONGODB_URL}. Error: {e}")
        print("INFO: MongoDB features will be unavailable. Using MOCK MongoDB (limited/no-op).")
        # You might choose to not initialize Beanie here or handle it differently.
        # For now, we'll just set the flag and db_client to None.
        # Operations relying on Beanie will likely fail or need to be adapted.
        db_client = None # Ensure db_client is None
        settings.MONGODB_AVAILABLE = False
        # Using a full in-memory Beanie is complex. For now, services would need
        # to check settings.MONGODB_AVAILABLE.


async def close_db():
    """Closes the MongoDB connection if it exists."""
    global db_client
    if db_client:
        try:
            db_client.close()
            print("INFO: MongoDB connection closed.")
        except Exception as e:
            print(f"ERROR: Error closing MongoDB connection: {e}")