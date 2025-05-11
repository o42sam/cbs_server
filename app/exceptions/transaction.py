# app/exceptions/transaction.py
from .base import AppException

class TransactionError(AppException):
    """Base exception for transaction-related errors."""
    pass

class TransactionNotFoundError(TransactionError):
    """Raised when a transaction is not found."""
    def __init__(self, transaction_id: str):
        super().__init__(message=f"Transaction with ID '{transaction_id}' not found.")
        self.transaction_id = transaction_id

class InvalidTransactionTypeError(TransactionError):
    """Raised when an invalid transaction type is provided."""
    def __init__(self, type_provided: str, allowed_types: list):
        super().__init__(message=f"Invalid transaction type '{type_provided}'. Allowed types are: {', '.join(allowed_types)}.")
        self.type_provided = type_provided

class TransactionUpdateError(TransactionError):
    """Raised when updating a transaction fails."""
    def __init__(self, transaction_id: str, detail: str):
        super().__init__(message=f"Failed to update transaction '{transaction_id}': {detail}.")
        self.transaction_id = transaction_id

class TransactionDeletionError(TransactionError):
    """Raised when deleting a transaction fails."""
    def __init__(self, transaction_id: str, detail: str):
        super().__init__(message=f"Failed to delete transaction '{transaction_id}': {detail}.")
        self.transaction_id = transaction_id

class ExternalTransferValidationError(TransactionError):
    """Raised when validation for external transfer details fails."""
    def __init__(self, detail: str):
        super().__init__(message=f"External transfer validation failed: {detail}")

class TransactionProcessingError(TransactionError):
    """Raised during issues in processing a transaction, e.g., during a transfer."""
    def __init__(self, detail: str):
        super().__init__(message=f"Transaction processing failed: {detail}")

# Existing TransactionFailedError can be used or replaced by TransactionProcessingError
# For consistency, let's assume TransactionFailedError is the one to use for general processing failures if specific ones don't apply.
# If TransactionFailedError was meant for a different scope, then TransactionProcessingError is a good addition.
# Given the context, TransactionProcessingError might be more specific to the act of processing,
# while TransactionFailedError could be a more general status. I'll add TransactionProcessingError.