# app/services/transaction.py
from datetime import datetime
from beanie import PydanticObjectId, Link, WriteRules
from beanie.odm.operators.find.comparison import In
from motor.motor_asyncio import AsyncIOMotorClientSession # type: ignore
from typing import List, Optional, Dict, Any, Union

from app.core.config import settings # Import settings
from app.services.account import AccountService # DEFAULT_CURRENCIES is in AccountService now
from app.schemas.user import User
from app.schemas.transaction import Transaction as DBTransaction
from app.schemas.account import Account
from app.api.v1.schemas.transaction import TransactionCreate # API Schema

from app.exceptions.account import (
    AccountNotFoundError, InsufficientFundsError, DailyLimitExceededError,
    AccountStatusError, BalanceLimitExceededError, SameAccountTransferError,
    CurrencyMismatchError, InvalidAmountError
)
from app.exceptions.user import UnauthorizedError
from app.exceptions.base import AppException, DatabaseUnavailableError # Or the correct path
from app.exceptions.transaction import (
    TransactionNotFoundError, InvalidTransactionTypeError, TransactionUpdateError,
    ExternalTransferValidationError, TransactionProcessingError, TransactionDeletionError
)

from app.database.mongodb import db_client # For explicit transactions

class TransactionService:

    def __init__(self):
        self.account_service = AccountService()

    async def _validate_and_get_account(self, identifier: str, user_for_auth: Optional[User] = None, check_ownership: bool = False, session=None) -> Account:
        # This will call AccountService._get_account, which has DB availability checks
        account = await self.account_service._get_account(identifier, fetch_links=True) # fetch_links=True to get user_id
        if user_for_auth and check_ownership:
            # Ensure link is fetched if MongoDB is available
            if isinstance(account.user_id, Link) and not account.user_id.is_fetched:
                if not settings.MONGODB_AVAILABLE: # Cannot fetch if DB down
                    raise DatabaseUnavailableError(db_name="MongoDB", operation="fetch linked user for account validation")
                await account.fetch_link(Account.user_id, session=session) # type: ignore
            
            if not isinstance(account.user_id, User) or account.user_id.id != user_for_auth.id:
                raise UnauthorizedError("User does not own the specified account.")
        return account

    async def create_transaction_record(
        self,
        transaction_data: TransactionCreate,
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> DBTransaction:
        if not settings.MONGODB_AVAILABLE:
            raise DatabaseUnavailableError(db_name="MongoDB", operation="create transaction record")

        db_transaction = DBTransaction(
            amount=transaction_data.amount,
            currency=transaction_data.currency.upper(),
            transaction_type=transaction_data.transaction_type,
            status=transaction_data.status,
            description=transaction_data.description,
            source_account_id=transaction_data.source_account_id, # type: ignore
            destination_account_id=transaction_data.destination_account_id, # type: ignore
            source_details=transaction_data.source_details,
            destination_details=transaction_data.destination_details,
            metadata=transaction_data.metadata,
            # created and updated have default_factory
        )
        await db_transaction.insert(session=session) # type: ignore
        return db_transaction

    async def transfer_funds(
        self,
        source_account_identifier: str,
        amount: float,
        currency: str,
        requesting_user: User,
        destination_account_identifier: Optional[str] = None,
        destination_details: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DBTransaction:
        if not settings.MONGODB_AVAILABLE:
            raise DatabaseUnavailableError(db_name="MongoDB", operation="transfer funds")
        if not db_client: # db_client would be None if MONGODB_URL was missing or initial connection failed
             raise DatabaseUnavailableError(db_name="MongoDB Client", operation="transfer funds (client not initialized)")


        if amount <= 0:
            raise InvalidAmountError("Transfer amount must be positive.")

        async with await db_client.start_session() as session:
            async with session.start_transaction():
                try:
                    source_account = await self._validate_and_get_account(
                        source_account_identifier,
                        user_for_auth=requesting_user,
                        check_ownership=True,
                        session=session
                    )

                    if source_account.currency.code.upper() != currency.upper():
                        raise CurrencyMismatchError(
                            source_currency=source_account.currency.code,
                            dest_currency=currency
                        )

                    await self.account_service.check_debit_conditions(source_account, amount)

                    transaction_status = "completed"
                    dest_account_resolved_id: Optional[PydanticObjectId] = None

                    if destination_account_identifier: # Internal Transfer
                        # Prevent self-transfer using resolved IDs
                        _temp_dest_acc_check = await self.account_service._get_account(destination_account_identifier, fetch_links=False) # Minimal fetch
                        if source_account.id == _temp_dest_acc_check.id:
                             raise SameAccountTransferError()

                        dest_account = await self.account_service._get_account(destination_account_identifier, fetch_links=False)

                        if source_account.currency.code != dest_account.currency.code:
                            raise CurrencyMismatchError(
                                source_currency=source_account.currency.code,
                                dest_currency=dest_account.currency.code
                            )
                        await self.account_service.check_credit_conditions(dest_account, amount)
                        
                        await self.account_service.perform_debit(source_account, amount, session=session)
                        await self.account_service.perform_credit(dest_account, amount, session=session)
                        
                        await source_account.save(session=session) # type: ignore
                        await dest_account.save(session=session) # type: ignore
                        dest_account_resolved_id = dest_account.id # type: ignore
                        transaction_status = "completed"

                    elif destination_details: # External Transfer
                        if not destination_details.get("bank_name") or not destination_details.get("account_number"):
                            raise ExternalTransferValidationError("Bank name and account number are required.")
                        
                        await self.account_service.perform_debit(source_account, amount, session=session)
                        await source_account.save(session=session) # type: ignore
                        
                        transaction_status = "pending_external"
                        print(f"Placeholder: Initiating external transfer of {amount} {currency} to {destination_details}")
                    else:
                        raise TransactionProcessingError("Invalid transfer: No destination specified.")

                    final_description = description or f"Transfer from {source_account.account_number}"
                    # ... (description logic remains same)

                    transaction_record_data = TransactionCreate( # Use Pydantic model for validation before DBTransaction
                        amount=amount,
                        currency=currency.upper(),
                        transaction_type="transfer",
                        status=transaction_status,
                        description=final_description,
                        source_account_id=source_account.id, # type: ignore
                        destination_account_id=dest_account_resolved_id,
                        destination_details=destination_details if not destination_account_identifier else None,
                        metadata=metadata,
                        # created and updated will be set by DBTransaction model's default_factory
                    )
                    # Create and insert the DBTransaction model
                    transaction_db_obj = DBTransaction(**transaction_record_data.model_dump(exclude_none=True))
                    await transaction_db_obj.insert(session=session) # type: ignore
                    return transaction_db_obj

                except (AccountNotFoundError, InsufficientFundsError, DailyLimitExceededError,
                        BalanceLimitExceededError, AccountStatusError, UnauthorizedError,
                        SameAccountTransferError, CurrencyMismatchError, InvalidAmountError,
                        ExternalTransferValidationError, TransactionProcessingError, DatabaseUnavailableError, AppException) as e: # type: ignore
                    # No need to call session.abort_transaction() explicitly, context manager handles it on exception
                    print(f"Transfer failed during transaction block: {type(e).__name__}: {e}")
                    raise e # Re-raise the original, more specific exception
                except Exception as e: # Catch any other unexpected error
                    print(f"Unexpected error during transfer transaction: {type(e).__name__} - {e}")
                    raise TransactionProcessingError(f"An internal error occurred during the transfer: {str(e)}")


    async def get_transaction_by_id(self, transaction_id: PydanticObjectId, requesting_user: User) -> DBTransaction:
        if not settings.MONGODB_AVAILABLE:
            # print(f"WARNING: MongoDB not available. Cannot get transaction {transaction_id}.")
            # return None # Or raise error
            raise DatabaseUnavailableError(db_name="MongoDB", operation=f"get transaction {transaction_id}")

        transaction = await DBTransaction.get(transaction_id, fetch_links=True) # type: ignore
        if not transaction:
            raise TransactionNotFoundError(transaction_id=str(transaction_id))

        if requesting_user.is_admin:
            return transaction # type: ignore

        is_involved = False
        # Check source account
        if transaction.source_account_id: # type: ignore
            # Ensure the link is fetched to access user_id
            source_acc_link = transaction.source_account_id # type: ignore
            if isinstance(source_acc_link, Link) and not source_acc_link.is_fetched: # type: ignore
                if not settings.MONGODB_AVAILABLE:
                    raise DatabaseUnavailableError(db_name="MongoDB", operation="fetch linked source account for transaction auth")
                await transaction.fetch_link(DBTransaction.source_account_id) # type: ignore
            
            if isinstance(transaction.source_account_id, Account) and isinstance(transaction.source_account_id.user_id, User): # type: ignore
                if transaction.source_account_id.user_id.id == requesting_user.id: # type: ignore
                    is_involved = True
            elif isinstance(transaction.source_account_id, Account) and isinstance(transaction.source_account_id.user_id, Link): # type: ignore
                 # If user_id itself is a link and needs fetching (less common for this setup but possible)
                if transaction.source_account_id.user_id.id == requesting_user.id: # type: ignore
                    is_involved = True


        # Check destination account if not already involved
        if not is_involved and transaction.destination_account_id: # type: ignore
            dest_acc_link = transaction.destination_account_id # type: ignore
            if isinstance(dest_acc_link, Link) and not dest_acc_link.is_fetched: # type: ignore
                if not settings.MONGODB_AVAILABLE:
                    raise DatabaseUnavailableError(db_name="MongoDB", operation="fetch linked destination account for transaction auth")
                await transaction.fetch_link(DBTransaction.destination_account_id) # type: ignore

            if isinstance(transaction.destination_account_id, Account) and isinstance(transaction.destination_account_id.user_id, User): # type: ignore
                if transaction.destination_account_id.user_id.id == requesting_user.id: # type: ignore
                    is_involved = True
            elif isinstance(transaction.destination_account_id, Account) and isinstance(transaction.destination_account_id.user_id, Link): # type: ignore
                if transaction.destination_account_id.user_id.id == requesting_user.id: # type: ignore
                    is_involved = True
        
        if not is_involved:
            raise UnauthorizedError("You do not have permission to view this transaction.")
        return transaction # type: ignore

    async def list_transactions(
        self, requesting_user: User, account_id: Optional[PydanticObjectId] = None,
        transaction_type: Optional[str] = None, status: Optional[str] = None,
        skip: int = 0, limit: int = 100
    ) -> List[DBTransaction]:
        if not settings.MONGODB_AVAILABLE:
            # print("WARNING: MongoDB not available. Cannot list transactions.")
            # return []
            raise DatabaseUnavailableError(db_name="MongoDB", operation="list transactions")

        query_conditions = []
        if requesting_user.is_admin:
            if account_id:
                query_conditions.append(
                    (DBTransaction.source_account_id.id == account_id) | \
                    (DBTransaction.destination_account_id.id == account_id) # type: ignore
                )
        else:
            user_accounts = await self.account_service.get_user_accounts(user_id=requesting_user.id) # type: ignore
            user_account_ids = [acc.id for acc in user_accounts]
            if not user_account_ids: return []

            if account_id:
                if account_id not in user_account_ids:
                    raise UnauthorizedError("Account specified for transaction listing is not owned by user.")
                query_conditions.append(
                    (DBTransaction.source_account_id.id == account_id) | \
                    (DBTransaction.destination_account_id.id == account_id) # type: ignore
                )
            else:
                query_conditions.append(
                    In(DBTransaction.source_account_id.id, user_account_ids) | \
                    In(DBTransaction.destination_account_id.id, user_account_ids) # type: ignore
                )
        
        if transaction_type:
            query_conditions.append(DBTransaction.transaction_type == transaction_type.lower())
        if status:
            query_conditions.append(DBTransaction.status == status.lower())

        query = DBTransaction.find(*query_conditions, fetch_links=True).sort(-DBTransaction.created).skip(skip).limit(limit)
        return await query.to_list() # type: ignore

    async def update_transaction(
        self, transaction_id: PydanticObjectId, update_data: Dict[str, Any], requesting_user: User
    ) -> DBTransaction:
        if not settings.MONGODB_AVAILABLE:
            raise DatabaseUnavailableError(db_name="MongoDB", operation=f"update transaction {transaction_id}")
        
        transaction = await self.get_transaction_by_id(transaction_id, requesting_user) # Handles DB check & auth

        if not requesting_user.is_admin:
            if transaction.status not in ["pending", "pending_external"]: # type: ignore
                raise TransactionUpdateError(str(transaction_id), "User can only update pending transactions.")
            if "status" in update_data and update_data["status"] is not None:
                raise TransactionUpdateError(str(transaction_id), "User cannot change transaction status.")

        update_fields = {k: v for k, v in update_data.items() if v is not None and hasattr(transaction, k)}
        if not update_fields: return transaction # type: ignore

        for field, value in update_fields.items():
            setattr(transaction, field, value)
        
        transaction.updated = datetime.utcnow() # type: ignore
        await transaction.save() # type: ignore
        return transaction # type: ignore

    async def delete_transaction(self, transaction_id: PydanticObjectId, requesting_user: User) -> bool:
        if not settings.MONGODB_AVAILABLE:
            raise DatabaseUnavailableError(db_name="MongoDB", operation=f"delete transaction {transaction_id}")

        if not requesting_user.is_admin:
            raise UnauthorizedError("Only administrators can delete transactions.")

        transaction = await DBTransaction.get(transaction_id) # type: ignore
        if not transaction:
            raise TransactionNotFoundError(transaction_id=str(transaction_id))
        
        if transaction.status == "completed" and transaction.transaction_type == "transfer": # type: ignore
            raise TransactionDeletionError(str(transaction_id), "Completed transfers cannot be hard-deleted.")

        delete_result = await transaction.delete() # type: ignore
        return delete_result.deleted_count > 0 if delete_result else False

    async def get_account_transactions(self, account_id: PydanticObjectId, user: User, skip: int = 0, limit: int = 25) -> List[DBTransaction]:
        if not settings.MONGODB_AVAILABLE:
            # print(f"WARNING: MongoDB not available. Cannot get transactions for account {account_id}.")
            # return []
            raise DatabaseUnavailableError(db_name="MongoDB", operation=f"get transactions for account {account_id}")
        
        # Auth check: ensure user owns the account or is admin
        # AccountService.get_account_by_id will handle this and DB availability for the account itself.
        await self.account_service.get_account_by_id(account_id, requesting_user=user, fetch_links=False)
        
        transactions = await DBTransaction.find(
            (DBTransaction.source_account_id.id == account_id) | (DBTransaction.destination_account_id.id == account_id), # type: ignore
            fetch_links=True
        ).sort(-DBTransaction.created).skip(skip).limit(limit).to_list()
        return transactions # type: ignore