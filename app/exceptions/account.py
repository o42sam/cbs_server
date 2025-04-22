
from .base import AppException

class AccountError(AppException):
    """Base exception for account-related errors."""
    pass

class AccountNotFoundError(AccountError):
    """Raised when an account is not found."""
    def __init__(self, identifier: str):
        super().__init__(message=f"Account with identifier '{identifier}' not found.")
        self.identifier = identifier

class InsufficientFundsError(AccountError):
    """Raised when an account has insufficient funds for a debit operation."""
    def __init__(self, account_id: str, needed: float, available: float):
        super().__init__(message=f"Insufficient funds in account {account_id}. Required: {needed}, Available: {available}.")
        self.account_id = account_id
        self.needed = needed
        self.available = available

class DailyLimitExceededError(AccountError):
    """Raised when a debit operation exceeds the daily limit."""
    def __init__(self, account_id: str, attempted: float, limit: float, daily_total: float):
        super().__init__(message=f"Daily debit limit exceeded for account {account_id}. Attempted: {attempted}, Limit: {limit}, Already Spent Today: {daily_total}.")
        self.account_id = account_id
        self.attempted = attempted
        self.limit = limit
        self.daily_total = daily_total

class BalanceLimitExceededError(AccountError):
    """Raised when a credit operation exceeds the account balance limit."""
    def __init__(self, account_id: str, attempted: float, limit: float, current_balance: float):
        super().__init__(message=f"Account balance limit exceeded for account {account_id}. Attempted Credit: {attempted}, Limit: {limit}, Current Balance: {current_balance}.")
        self.account_id = account_id
        self.attempted = attempted
        self.limit = limit
        self.current_balance = current_balance

class AccountStatusError(AccountError):
    """Raised when an operation is not allowed due to the account's status."""
    def __init__(self, account_id: str, operation: str, status: str, reason: str = ""):
        message = f"Operation '{operation}' not allowed for account {account_id} due to status: '{status}'."
        if reason:
            message += f" Reason: {reason}"
        super().__init__(message=message)
        self.account_id = account_id
        self.operation = operation
        self.status = status

class InvalidAccountTypeError(AccountError):
    """Raised when an invalid account type is provided."""
    def __init__(self, invalid_type: str, allowed_types: list):
        super().__init__(message=f"Invalid account type '{invalid_type}'. Allowed types are: {', '.join(allowed_types)}")
        self.invalid_type = invalid_type

class InvalidCurrencyError(AccountError):
    """Raised when invalid currency details are provided."""
    def __init__(self, detail: str):
        super().__init__(message=f"Invalid currency configuration: {detail}")

class SameAccountTransferError(AccountError):
    """Raised when source and destination accounts are the same."""
    def __init__(self):
        super().__init__(message="Source and destination accounts cannot be the same.")

class CurrencyMismatchError(AccountError):
    """Raised during transfer if account currencies do not match."""
    def __init__(self, source_currency: str, dest_currency: str):
        super().__init__(message=f"Currency mismatch: Cannot transfer {source_currency} to {dest_currency} directly.")

class InvalidAmountError(AccountError):
    """Raised when an invalid amount (e.g., non-positive) is used."""
    def __init__(self, detail: str = "Amount must be positive."):
        super().__init__(message=detail)

class InvalidLimitValueError(AccountError):
    """Raised when setting invalid limit values."""
    def __init__(self, detail: str = "Limit values must be non-negative."):
        super().__init__(message=detail)