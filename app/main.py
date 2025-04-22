
from fastapi import FastAPI, status, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from contextlib import asynccontextmanager

from app.core.config import settings
from app.database.mongodb import init_db, db_client
from app.api.v1.endpoints import auth, user, account, transaction, admin


from app.exceptions.base import AppException
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

    print("Starting up...")
    await init_db()
    print("Database initialized.")
    yield

    print("Shutting down...")



    print("Shutdown complete.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS if settings.ALLOWED_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Handles custom application exceptions based on their type."""
    status_code = status.HTTP_400_BAD_REQUEST


    if isinstance(exc, UserNotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, UserAlreadyExistsError):
        status_code = status.HTTP_409_CONFLICT
    elif isinstance(exc, InvalidCredentialsError):
         status_code = status.HTTP_401_UNAUTHORIZED
    elif isinstance(exc, UnauthorizedError):

         status_code = status.HTTP_403_FORBIDDEN


    elif isinstance(exc, AccountNotFoundError):
         status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, (InsufficientFundsError, DailyLimitExceededError,
                         BalanceLimitExceededError, AccountStatusError,
                         SameAccountTransferError, CurrencyMismatchError,
                         InvalidAmountError, InvalidLimitValueError,
                         InvalidAccountTypeError, InvalidCurrencyError)):

         status_code = status.HTTP_400_BAD_REQUEST



    return JSONResponse(
        status_code=status_code,
        content={"detail": exc.message},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handles FastAPI request validation errors (e.g., invalid input types)."""

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": exc.body},
    )

@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
    """Handles Pydantic validation errors raised manually or deeper in the application."""

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": exc.errors()},
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handles standard FastAPI HTTPExceptions raised directly in endpoints."""


    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handles any other unexpected errors (catch-all)."""

    import traceback
    print(f"Unhandled exception: {type(exc).__name__} - {exc}")
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



@app.get("/", tags=["Root"])
async def read_root():
    return {"message": f"Welcome to {settings.PROJECT_NAME}"}


if __name__ == "__main__":
    import uvicorn

    host = getattr(settings, "SERVER_HOST", "0.0.0.0")
    port = getattr(settings, "SERVER_PORT", 8000)
    uvicorn.run(app, host=host, port=port, reload=True)