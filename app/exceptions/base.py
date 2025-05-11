from typing import Optional

class AppException(Exception):
    """Base class for custom application exceptions."""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)
        
class DatabaseUnavailableError(AppException): # Make sure it inherits from your base AppException
    def __init__(self, db_name: str = "Database", operation: Optional[str] = None):
        message = f"{db_name} is currently unavailable."
        if operation:
            message += f" The operation '{operation}' could not be completed."
        # For a 503 Service Unavailable status:
        # super().__init__(message, status_code=503) # If your AppException handles status_code
        super().__init__(message) # Adjust if status_code is handled differently