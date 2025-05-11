# app/main.py
from fastapi import FastAPI, status, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
# from pydantic import ValidationError # Already imported via RequestValidationError or not strictly needed here
from contextlib import asynccontextmanager

# Crucially, import settings AFTER potential .env loading by pydantic-settings
from app.core.config import settings # Settings instance

# Import database initializers and closers
from app.database.mongodb import init_db as init_mongodb, close_db as close_mongodb, db_client
from app.database.redis import init_redis, close_redis, redis_client

from app.api.v1.endpoints import auth, user, account, transaction # Removed admin for now if not defined

from app.exceptions.base import AppException, DatabaseUnavailableError
from app.exceptions.user import (
    UserNotFoundError, UserAlreadyExistsError, UnauthorizedError, InvalidCredentialsError
)
from app.exceptions.account import (
    AccountError, AccountNotFoundError, InsufficientFundsError, DailyLimitExceededError,
    BalanceLimitExceededError, AccountStatusError, SameAccountTransferError,
    CurrencyMismatchError, InvalidAmountError, InvalidLimitValueError,
    InvalidAccountTypeError, InvalidCurrencyError
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown events."""
    print("INFO: Starting up application...")

    # Initialize MongoDB
    print("INFO: Initializing MongoDB connection...")
    await init_mongodb()
    if settings.MONGODB_AVAILABLE:
        print("INFO: MongoDB initialized successfully.")
    else:
        print("WARNING: MongoDB is not available. Application will run with limited functionality.")
        # Consider adding more specific mock setup here if needed,
        # or ensure services handle db_client being None or settings.MONGODB_AVAILABLE == False

    # Initialize Redis
    print("INFO: Initializing Redis connection...")
    await init_redis()
    if settings.REDIS_AVAILABLE:
        print("INFO: Redis initialized successfully.")
    else:
        print("WARNING: Redis is not available or not configured. Using mock Redis if applicable.")
        # Services should check redis_client or settings.REDIS_AVAILABLE

    yield

    print("INFO: Shutting down application...")
    await close_redis()
    await close_mongodb()
    print("INFO: Shutdown complete.")


# Initialize FastAPI app
# Settings should be loaded when app.core.config.settings is imported
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS, # Use the loaded setting
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers remain largely the same, but ensure they don't
# assume database availability if they log to DB for example.

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    status_code = status.HTTP_400_BAD_REQUEST
    if isinstance(exc, UserNotFoundError): status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, UserAlreadyExistsError): status_code = status.HTTP_409_CONFLICT
    elif isinstance(exc, InvalidCredentialsError): status_code = status.HTTP_401_UNAUTHORIZED
    elif isinstance(exc, UnauthorizedError): status_code = status.HTTP_403_FORBIDDEN
    elif isinstance(exc, AccountNotFoundError): status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, (InsufficientFundsError, DailyLimitExceededError,
                          BalanceLimitExceededError, AccountStatusError,
                          SameAccountTransferError, CurrencyMismatchError,
                          InvalidAmountError, InvalidLimitValueError,
                          InvalidAccountTypeError, InvalidCurrencyError)):
        status_code = status.HTTP_400_BAD_REQUEST
    return JSONResponse(status_code=status_code, content={"detail": exc.message})

@app.exception_handler(DatabaseUnavailableError)
async def database_unavailable_exception_handler(request: Request, exc: DatabaseUnavailableError):
    # Log the error server-side for monitoring
    print(f"ERROR: DatabaseUnavailableError: {exc.message} for request {request.url}")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, # 503 status code
        content={"detail": exc.message},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": exc.body},
    )

# This handles Pydantic ValidationErrors that might occur elsewhere, e.g. in services if you manually validate
# from pydantic import ValidationError as PydanticValError # Alias if needed
# @app.exception_handler(PydanticValError)
# async def pydantic_validation_exception_handler(request: Request, exc: PydanticValError):
#     return JSONResponse(
#         status_code=status.HTTP_400_BAD_REQUEST,
#         content={"detail": exc.errors()},
#     )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    import traceback
    print(f"CRITICAL: Unhandled exception: {type(exc).__name__} - {exc}")
    print(traceback.format_exc())
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected internal server error occurred."},
    )


API_PREFIX = settings.API_V1_STR

app.include_router(auth.router, prefix=f"{API_PREFIX}/auth", tags=["Auth"])
app.include_router(user.router, prefix=f"{API_PREFIX}/users", tags=["Users"])
app.include_router(account.router, prefix=f"{API_PREFIX}/accounts", tags=["Accounts"])
app.include_router(transaction.router, prefix=f"{API_PREFIX}/transactions", tags=["Transactions"])
# If you have admin endpoints:
# from app.api.v1.endpoints import admin as admin_router # example import
# app.include_router(admin_router.router, prefix=f"{API_PREFIX}/admin", tags=["Admin"])


@app.get("/", tags=["Root"])
async def read_root():
    db_status = "available" if settings.MONGODB_AVAILABLE else "unavailable (mock or limited functionality)"
    redis_status = "available" if settings.REDIS_AVAILABLE else "unavailable (mock or limited functionality)"
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "database_status": {
            "mongodb": db_status,
            "redis": redis_status
        }
    }

if __name__ == "__main__":
    import uvicorn
    # Settings are already loaded
    host = settings.SERVER_HOST
    port = settings.SERVER_PORT
    print(f"INFO: Starting Uvicorn server on {host}:{port}")
    uvicorn.run(app, host=host, port=port, reload=True)