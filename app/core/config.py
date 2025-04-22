from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Finance Management API"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    MONGODB_URL: str
    REDIS_URL: str
    ALLOWED_ORIGINS: list = ["*"]
    MODE: str = "vibe"

    model_dict = {
        "env_file": ".env"   
    }

settings = Settings()