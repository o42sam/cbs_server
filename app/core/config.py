# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "CBS Server"
    API_V1_STR: str = "/api/v1"

    # Environment variables
    SECRET_KEY: str
    MONGODB_URL: str
    REDIS_URL: Optional[str] = None # Make Redis URL optional for graceful fallback

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8 # 8 days
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    ALLOWED_ORIGINS: List[str] = ["*"] # Or specify your frontend origins

    # For 2FA in AuthService (example, adjust as needed)
    MODE: str = "normal" # "strict" or "normal"

    # Database availability flags (will be set at runtime)
    MONGODB_AVAILABLE: bool = False
    REDIS_AVAILABLE: bool = False

    # This tells pydantic-settings to load from a .env file
    model_config = SettingsConfigDict(env_file=".env", extra='ignore')

settings = Settings()