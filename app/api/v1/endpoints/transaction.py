# app/api/v1/endpoints/transaction.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional

from beanie import PydanticObjectId

from app.api.v1.schemas.transaction import (
    TransactionCreate, TransactionRead, TransactionUpdate,
    FundTransferRequest, FundTransferResponse
)
from app.schemas.user import User
from app.services.transaction import TransactionService
from app.api.v1.dependencies import get_current_user, get_current_admin

from app.exceptions.base import AppException
from app.exceptions.account import (
    AccountError, AccountNotFoundError, InsufficientFundsError, DailyLimitExceededError,
    BalanceLimitExceededError, AccountStatusError, SameAccountTransferError,
    CurrencyMismatchError, InvalidAmountError
)
from app.exceptions.user import UnauthorizedError
from app.exceptions.transaction import (
    TransactionError, TransactionNotFoundError as ServiceTransactionNotFoundError, # Alias to avoid clash
    InvalidTransactionTypeError, TransactionUpdateError, ExternalTransferValidationError,
    TransactionProcessingError, TransactionDeletionError
)

router = APIRouter()

async def get_transaction_service():
    return TransactionService()

@router.post(
    "/transfer",
    response_model=FundTransferResponse,
    status_code=status.HTTP_200_OK, # Or 201 if a new transaction resource is primarily created
    summary="Transfer funds between accounts or to an external destination"
)
async def transfer_funds_endpoint(
    transfer_data: FundTransferRequest,
    current_user: User = Depends(get_current_user),
    service: TransactionService = Depends(get_transaction_service)
):
    """
    Transfers a specified amount from the user's source account.
    Destination can be another internal account or external details (placeholder processing).
    Requires authentication. The user must own the source account.
    """
    try:
        transaction_record = await service.transfer_funds(
            source_account_identifier=transfer_data.source_account_identifier,
            amount=transfer_data.amount,
            currency=transfer_data.currency,
            requesting_user=current_user,
            destination_account_identifier=transfer_data.destination_account_identifier,
            destination_details=transfer_data.destination_details,
            description=transfer_data.description,
            metadata=transfer_data.metadata
        )
        
        message = "Transfer completed successfully."
        if transaction_record.status == "pending_external":
            message = "External transfer initiated, pending processing."

        return FundTransferResponse(
            message=message,
            transaction_id=transaction_record.id,
            status=transaction_record.status,
            timestamp=transaction_record.created,
            amount=transaction_record.amount,
            currency=transaction_record.currency,
            source_account_id=transaction_record.source_account_id.id, # Assuming source_account_id is Link
            destination_account_id=transaction_record.destination_account_id.id if transaction_record.destination_account_id else None,
            destination_details=transaction_record.destination_details
        )
    except (AccountNotFoundError, InsufficientFundsError, DailyLimitExceededError,
            BalanceLimitExceededError, AccountStatusError, SameAccountTransferError,
            CurrencyMismatchError, InvalidAmountError, ExternalTransferValidationError,
            TransactionProcessingError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except UnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)
    except AppException as e: # Catch other custom app exceptions
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except Exception as e:
        print(f"Unexpected error during funds transfer endpoint: {e}") # For logging
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred during the transfer.")

@router.post(
    "/",
    response_model=TransactionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a manual transaction record (Admin only or specific types)",
    dependencies=[Depends(get_current_admin)] # Example: Restrict generic creation
)
async def create_manual_transaction(
    transaction_in: TransactionCreate, # This schema needs careful thought for who can create what
    # current_user: User = Depends(get_current_user), # Or use current_user for specific types
    service: TransactionService = Depends(get_transaction_service)
):
    """
    Manually creates a transaction record.
    Primarily for administrative use or specific allowed transaction types by users (e.g., logging an expense).
    Requires authentication. Authorization might be type-dependent.
    NOTE: This endpoint does NOT move funds by itself. It's for record-keeping.
    Use the `/transfer` endpoint for fund movements.
    """
    try:
        # Add logic here to validate if the current_user can create this type of transaction
        # For example, if transaction_in.type == "manual_expense", ensure source_account_id is owned by user.
        # For now, assuming admin makes these or it's a simple log.

        # Ensure currency is uppercase
        transaction_in.currency = transaction_in.currency.upper()

        created_transaction = await service.create_transaction_record(transaction_data=transaction_in)
        return TransactionRead.model_validate(created_transaction) # Pydantic v2
    except ValueError as e: # Catches Pydantic validation errors if any slip or are raised in service
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except TransactionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except Exception as e:
        print(f"Unexpected error during manual transaction creation: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create transaction record.")


@router.get(
    "/{transaction_id}",
    response_model=TransactionRead,
    summary="Get a specific transaction by ID"
)
async def read_transaction(
    transaction_id: PydanticObjectId,
    current_user: User = Depends(get_current_user),
    service: TransactionService = Depends(get_transaction_service)
):
    """
    Retrieves details for a specific transaction by its ID.
    Requires authentication. Access is restricted to users involved in the transaction or administrators.
    """
    try:
        transaction = await service.get_transaction_by_id(transaction_id, current_user)
        return TransactionRead.model_validate(transaction)
    except ServiceTransactionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except UnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)
    except Exception as e:
        print(f"Unexpected error retrieving transaction {transaction_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve transaction.")

@router.get(
    "/",
    response_model=List[TransactionRead],
    summary="List transactions with optional filters"
)
async def list_transactions(
    current_user: User = Depends(get_current_user),
    service: TransactionService = Depends(get_transaction_service),
    account_id: Optional[PydanticObjectId] = Query(None, description="Filter by account ID (source or destination)"),
    transaction_type: Optional[str] = Query(None, description="Filter by transaction type (e.g., transfer, deposit)"),
    status: Optional[str] = Query(None, description="Filter by transaction status (e.g., completed, pending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of records to return")
):
    """
    Retrieves a list of transactions.
    - Regular users see transactions related to their accounts.
    - Administrators can see all transactions or filter by a specific account.
    Filtering by transaction_type and status is available.
    """
    try:
        transactions_db = await service.list_transactions(
            requesting_user=current_user,
            account_id=account_id,
            transaction_type=transaction_type,
            status=status,
            skip=skip,
            limit=limit
        )
        return [TransactionRead.model_validate(t) for t in transactions_db]
    except UnauthorizedError as e: # e.g. if user tries to filter by account_id not theirs
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)
    except ValueError as e: # For invalid filter values not caught by Pydantic
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        print(f"Unexpected error listing transactions: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list transactions.")


@router.put(
    "/{transaction_id}",
    response_model=TransactionRead,
    summary="Update a transaction (e.g., description, status - limited)"
)
async def update_transaction(
    transaction_id: PydanticObjectId,
    update_data: TransactionUpdate,
    current_user: User = Depends(get_current_user), # Admin/specific user logic in service
    service: TransactionService = Depends(get_transaction_service)
):
    """
    Updates limited fields of a transaction, such as its description or status (by admin).
    - Admins have more privileges to update.
    - Users might only be able to update specific fields on transactions in certain states.
    Requires authentication.
    """
    try:
        updated_transaction = await service.update_transaction(
            transaction_id, update_data.model_dump(exclude_unset=True), current_user
        )
        return TransactionRead.model_validate(updated_transaction)
    except ServiceTransactionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except UnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)
    except (TransactionUpdateError, ValueError) as e: # ValueError for Pydantic validation in schema
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        print(f"Unexpected error updating transaction {transaction_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update transaction.")


@router.delete(
    "/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a transaction (Admin only - use with caution)"
)
async def delete_transaction(
    transaction_id: PydanticObjectId,
    current_user: User = Depends(get_current_admin), # Restricted to admin
    service: TransactionService = Depends(get_transaction_service)
):
    """
    Deletes a transaction record.
    **Warning**: Financial transactions are typically not hard-deleted. Prefer marking as 'cancelled' or 'reversed'.
    This endpoint is restricted to administrators.
    """
    try:
        success = await service.delete_transaction(transaction_id, current_user)
        if not success:
            # This might occur if delete operation in DB returns 0 deleted_count for some reason
            # but get_transaction_by_id (called within delete_transaction) would have raised NotFoundError first.
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found or deletion failed.")
        return None # FastAPI handles 204 NO_CONTENT response
    except ServiceTransactionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except UnauthorizedError as e: # Should be caught by Depends(get_current_admin) but good for safety
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)
    except TransactionDeletionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except Exception as e:
        print(f"Unexpected error deleting transaction {transaction_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete transaction.")

# Get transactions for a specific account (could be part of account endpoint or here for transaction focus)
@router.get(
    "/account/{account_id}",
    response_model=List[TransactionRead],
    summary="Get all transactions for a specific account"
)
async def get_transactions_for_account(
    account_id: PydanticObjectId,
    current_user: User = Depends(get_current_user),
    service: TransactionService = Depends(get_transaction_service),
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100)
):
    """
    Retrieves all transactions associated with a specific account ID (either as source or destination).
    Requires authentication. User must own the account or be an administrator.
    """
    try:
        # The service.get_account_transactions already performs auth check via get_account_by_id
        transactions = await service.get_account_transactions(account_id, current_user, skip=skip, limit=limit)
        return [TransactionRead.model_validate(t) for t in transactions]
    except AccountNotFoundError as e: # Raised by account_service if account doesn't exist
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except UnauthorizedError as e: # Raised by account_service if user doesn't own account
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)
    except Exception as e:
        print(f"Unexpected error fetching transactions for account {account_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve account transactions.")