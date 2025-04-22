
from datetime import datetime
from beanie import PydanticObjectId, Link
from motor.motor_asyncio import AsyncIOMotorClientSession


from app.services.account import AccountService


from app.schemas.user import User
from app.schemas.transaction import Transaction
from app.schemas.account import Account
from typing import List


from app.exceptions.account import (
    AccountNotFoundError, InsufficientFundsError, DailyLimitExceededError,
    AccountStatusError, BalanceLimitExceededError, SameAccountTransferError,
    CurrencyMismatchError, InvalidAmountError
)
from app.exceptions.user import UnauthorizedError
from app.exceptions.base import AppException


from app.database.mongodb import db_client

class TransactionService:

    def __init__(self):

        self.account_service = AccountService()

    async def transfer_funds(
        self,
        source_identifier: str,
        dest_identifier: str,
        amount: float,
        requesting_user: User
    ) -> Transaction:
        """
        Transfers funds between two accounts after performing necessary checks.
        Uses database transactions for atomicity.
        """
        if amount <= 0:
            raise InvalidAmountError("Transfer amount must be positive.")



        async with await db_client.start_session() as session:
            async with session.start_transaction():
                try:


                    source_account = await self.account_service._get_account(source_identifier, fetch_links=True)
                    dest_account = await self.account_service._get_account(dest_identifier, fetch_links=False)



                    if not isinstance(source_account.user_id, User):
                         await source_account.fetch_link(Account.user_id, session=session)
                    if source_account.user_id.id != requesting_user.id:
                        raise UnauthorizedError("You do not have permission to transfer funds from this account.")


                    if source_account.id == dest_account.id:
                        raise SameAccountTransferError()

                    if source_account.currency.code != dest_account.currency.code:


                        raise CurrencyMismatchError(
                            source_currency=source_account.currency.code,
                            dest_currency=dest_account.currency.code
                        )


                    await self.account_service.check_debit_conditions(source_account, amount)
                    await self.account_service.check_credit_conditions(dest_account, amount)


                    await self.account_service.perform_debit(source_account, amount, session=session)
                    await self.account_service.perform_credit(dest_account, amount, session=session)


                    transaction = Transaction(
                        amount=amount,
                        currency=source_account.currency.code,
                        type="transfer",
                        status="completed",
                        description=f"Transfer from {source_account.account_number} to {dest_account.account_number}",
                        source_account_id=source_account.id,
                        destination_account_id=dest_account.id,
                        created=datetime.utcnow(),
                        updated=datetime.utcnow()

                    )
                    await transaction.insert(session=session)



                    await source_account.save(session=session)
                    await dest_account.save(session=session)



                    return transaction

                except (AccountNotFoundError, InsufficientFundsError, DailyLimitExceededError,
                        BalanceLimitExceededError, AccountStatusError, UnauthorizedError,
                        SameAccountTransferError, CurrencyMismatchError, InvalidAmountError,
                        AppException) as e:

                    print(f"Transfer failed: {type(e).__name__}: {e}")


                    raise e
                except Exception as e:

                    print(f"Unexpected error during transfer transaction: {e}")


                    raise AppException("An internal error occurred during the transfer. Please try again later.")

    async def get_account_transactions(self, account_id: PydanticObjectId, user: User) -> List[Transaction]:
        """Retrieves transaction history for a given account, checking permissions."""

        account = await self.account_service.get_account_by_id(account_id, requesting_user=user, fetch_links=False)



        transactions = await Transaction.find(
            (Transaction.source_account_id.id == account_id) | (Transaction.destination_account_id.id == account_id),

        ).sort(-Transaction.created).to_list()

        return transactions