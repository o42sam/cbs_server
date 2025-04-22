
from fastapi import APIRouter, Depends, HTTPException, status, Response
from typing import List
from beanie import PydanticObjectId, Link


from app.api.v1.schemas.account import (
    AccountCreate, AccountRead, AccountLimitUpdate, AccountStatusUpdate,
    AccountStatusRead, TransferRequest, TransferResponse, UserOwner
)

from app.schemas.user import User
from app.schemas.account import Account


from app.services.account import AccountService
from app.services.transaction import TransactionService
from app.api.v1.dependencies import get_current_user


from app.exceptions.account import (
    AccountError, AccountNotFoundError, InsufficientFundsError,
    DailyLimitExceededError, AccountStatusError, BalanceLimitExceededError,
    SameAccountTransferError, CurrencyMismatchError, InvalidAmountError,
    InvalidLimitValueError
)
from app.exceptions.user import UnauthorizedError
from app.exceptions.base import AppException

router = APIRouter()


async def get_account_service():
    return AccountService()


async def get_transaction_service():
    return TransactionService()



@router.post(
    "/",
    response_model=AccountRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new account for the current user"
)
async def create_account(
    account_data: AccountCreate,
    current_user: User = Depends(get_current_user),
    service: AccountService = Depends(get_account_service)
):
    """
    Creates a new bank account (`savings` or `current`) for the logged-in user.
    Requires authentication.
    """
    try:

        created_account = await service.create_account(
            user=current_user,
            account_type=account_data.type,
            currency_code=account_data.currency_code,
            balance_limit=account_data.balance_limit,
            daily_debit_limit=account_data.daily_debit_limit
        )

        user_owner = UserOwner(
            id=current_user.id,
            email=current_user.email,
            full_name=f"{current_user.first_name} {current_user.last_name}"
        )

        response_data = created_account.model_dump()
        response_data['user'] = user_owner
        return AccountRead(**response_data)

    except AccountError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except Exception as e:

        print(f"Account creation failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create account.")

@router.get(
    "/me",
    response_model=List[AccountRead],
    summary="Get all accounts for the current user"
)
async def read_my_accounts(
    current_user: User = Depends(get_current_user),
    service: AccountService = Depends(get_account_service)
):
    """
    Retrieves a list of all bank accounts associated with the currently authenticated user.
    Requires authentication.
    """
    accounts = await service.get_user_accounts(user_id=current_user.id)

    response_list = []
    user_owner = UserOwner(
        id=current_user.id,
        email=current_user.email,
        full_name=f"{current_user.first_name} {current_user.last_name}"
    )
    for acc in accounts:
        acc_data = acc.model_dump()
        acc_data['user'] = user_owner
        response_list.append(AccountRead(**acc_data))

    return response_list

@router.get(
    "/{account_id}",
    response_model=AccountRead,
    summary="Get a specific account by ID"
)
async def read_account(
    account_id: PydanticObjectId,
    current_user: User = Depends(get_current_user),
    service: AccountService = Depends(get_account_service)
):
    """
    Retrieves details for a specific account ID.
    Requires authentication. Access is restricted to the account owner or an administrator.
    """
    try:
        account = await service.get_account_by_id(account_id, current_user, fetch_links=True)



        if isinstance(account.user_id, Link):



             pass

        owner_user = account.user_id
        user_owner_data = UserOwner(
            id=owner_user.id,
            email=owner_user.email,
            full_name=f"{owner_user.first_name} {owner_user.last_name}"
        )
        acc_data = account.model_dump()
        acc_data['user'] = user_owner_data
        return AccountRead(**acc_data)

    except AccountNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except UnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)
    except AccountError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.put(
    "/{account_id}/limits",
    response_model=AccountRead,
    summary="Update account limits"
)
async def update_account_limits(
    account_id: PydanticObjectId,
    limit_data: AccountLimitUpdate,
    current_user: User = Depends(get_current_user),
    service: AccountService = Depends(get_account_service)
):
    """
    Updates the balance limit and/or daily debit limit for a specific account.
    Requires authentication. Must be the account owner or an administrator.
    """
    try:
        updated_account = await service.update_account_limits(
            account_id=account_id,
            requesting_user=current_user,
            balance_limit=limit_data.balance_limit,
            daily_debit_limit=limit_data.daily_debit_limit
        )

        await updated_account.fetch_link(Account.user_id)
        owner_user = updated_account.user_id
        user_owner_data = UserOwner(
             id=owner_user.id,
             email=owner_user.email,
             full_name=f"{owner_user.first_name} {owner_user.last_name}"
        )
        acc_data = updated_account.model_dump()
        acc_data['user'] = user_owner_data
        return AccountRead(**acc_data)

    except AccountNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except UnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)
    except InvalidLimitValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except AccountError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.put(
    "/{account_id}/status",
    response_model=AccountRead,
    summary="Update account status (Admin only)"
)
async def update_account_status(
    account_id: PydanticObjectId,
    status_data: AccountStatusUpdate,
    current_user: User = Depends(get_current_user),
    service: AccountService = Depends(get_account_service)
):
    """
    Updates the status (`unrestricted`, `restricted`, `frozen`) of an account.
    Requires administrator privileges.
    """
    try:
        updated_account = await service.update_account_status(
            account_id=account_id,
            requesting_user=current_user,
            status=status_data.status,
            description=status_data.description
        )

        await updated_account.fetch_link(Account.user_id)
        owner_user = updated_account.user_id
        user_owner_data = UserOwner(
             id=owner_user.id,
             email=owner_user.email,
             full_name=f"{owner_user.first_name} {owner_user.last_name}"
        )
        acc_data = updated_account.model_dump()
        acc_data['user'] = user_owner_data
        return AccountRead(**acc_data)

    except AccountNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except UnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)
    except ValueError as e:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except AccountError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

@router.get(
    "/{account_id}/status",
    response_model=AccountStatusRead,
    summary="Get account status"
)
async def get_account_status(
    account_id: PydanticObjectId,
    current_user: User = Depends(get_current_user),
    service: AccountService = Depends(get_account_service)
):
    """
    Retrieves the current status (`unrestricted`, `restricted`, `frozen`) of an account.
    Requires authentication. Must be the account owner or an administrator.
    """
    try:


        account = await service.get_account_by_id(account_id, current_user, fetch_links=False)
        status_obj = await service.get_account_status(account_id, current_user)

        return AccountStatusRead(
            account_number=account.account_number,
            status=status_obj.status,
            description=status_obj.description
        )
    except AccountNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except UnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)
    except AccountError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.delete(
    "/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an account"
)
async def delete_account(
    account_id: PydanticObjectId,
    current_user: User = Depends(get_current_user),
    service: AccountService = Depends(get_account_service)
):
    """
    Deletes a specific account by ID.
    Requires authentication. Must be the account owner or an administrator.
    The account balance must be zero before deletion is allowed.
    """
    try:
        deleted = await service.delete_account(account_id, current_user)
        if not deleted:


             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found or deletion failed.")

        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except AccountNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except UnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)
    except AccountStatusError as e:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except AccountError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)




@router.post(
    "/transfer",
    response_model=TransferResponse,
    summary="Transfer funds between accounts"
)
async def transfer_funds(
    transfer_data: TransferRequest,
    current_user: User = Depends(get_current_user),

    service: TransactionService = Depends(get_transaction_service)
):
    """
    Transfers a specified amount from the user's source account to a destination account.
    Requires authentication. The user must own the source account.
    Uses Account ID or Account Number for source/destination identifiers.
    """
    try:
        transaction_record = await service.transfer_funds(
            source_identifier=transfer_data.source_identifier,
            dest_identifier=transfer_data.destination_identifier,
            amount=transfer_data.amount,
            requesting_user=current_user
        )

        return TransferResponse(
            message="Transfer successful",
            transaction_id=transaction_record.id,
            source_account_id=transaction_record.source_account_id.id,
            destination_account_id=transaction_record.destination_account_id.id,
            amount=transaction_record.amount,
            currency=transaction_record.currency,
            timestamp=transaction_record.created
        )

    except (AccountNotFoundError, InsufficientFundsError, DailyLimitExceededError,
            BalanceLimitExceededError, AccountStatusError, SameAccountTransferError,
            CurrencyMismatchError, InvalidAmountError) as e:

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except UnauthorizedError as e:

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)
    except AppException as e:

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except Exception as e:

        print(f"Unexpected error during funds transfer: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred during the transfer.")