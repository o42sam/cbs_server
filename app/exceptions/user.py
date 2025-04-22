
from .base import AppException

class UserNotFoundError(AppException):
    """Raised when a user is not found in the database."""
    def __init__(self, identifier: str):
        super().__init__(message=f"User with identifier '{identifier}' not found.")
        self.identifier = identifier

class UserAlreadyExistsError(AppException):
    """Raised when attempting to create a user that already exists (e.g., duplicate email)."""
    def __init__(self, email: str):
        super().__init__(message=f"User with email '{email}' already exists.")
        self.email = email

class UnauthorizedError(AppException):
    """Raised for authorization failures."""
    def __init__(self, detail: str = "Not authorized to perform this action."):
        super().__init__(message=detail)

class InvalidCredentialsError(AppException):
    """Raised for invalid login credentials."""
    def __init__(self, detail: str = "Invalid credentials."):
        super().__init__(message=detail)