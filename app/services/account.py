
from beanie import PydanticObjectId, Link, WriteRules
from beanie.exceptions import DocumentNotFound
from typing import List, Optional
from datetime import datetime, date

from app.schemas.account import Account, Currency, AccountStatus
from app.schemas.user import User
from app.exceptions.account import (
    AccountNotFoundError, InsufficientFundsError, DailyLimitExceededError,
    BalanceLimitExceededError, AccountStatusError, InvalidAccountTypeError,
    InvalidCurrencyError, InvalidLimitValueError
)
from app.exceptions.user import UnauthorizedError


ALLOWED_ACCOUNT_TYPES = ["savings", "current"]
ALLOWED_STATUSES = ["unrestricted", "restricted", "frozen"]
DEFAULT_CURRENCIES = {
    "NGN": Currency(name="Nigerian Naira", code="NGN", symbol="₦"),
    "USD": Currency(name="US Dollar", code="USD", symbol="$"),

}

class AccountService:

    async def _get_account(self, identifier: str, fetch_links: bool = False) -> Account:
        """Helper to get account by ID or number."""
        try:
            account = await Account.get(PydanticObjectId(identifier), fetch_links=fetch_links)
            if account:

                if fetch_links and isinstance(account.user_id, Link) and not account.user_id.is_fetched:
                    await account.fetch_link(Account.user_id)
                return account
        except (ValueError, TypeError, DocumentNotFound):
            pass

        account = await Account.find_one(Account.account_number == identifier, fetch_links=fetch_links)
        if not account:
            raise AccountNotFoundError(identifier=identifier)


        if fetch_links and isinstance(account.user_id, Link) and not account.user_id.is_fetched:
             await account.fetch_link(Account.user_id)
        return account

    async def create_account(
        self,
        user: User,
        account_type: str,
        currency_code: str = "NGN",
        balance_limit: Optional[float] = None,
        daily_debit_limit: Optional[float] = None
    ) -> Account:
        """Creates a new bank account for a user."""
        if account_type.lower() not in ALLOWED_ACCOUNT_TYPES:
            raise InvalidAccountTypeError(invalid_type=account_type, allowed_types=ALLOWED_ACCOUNT_TYPES)

        currency_obj = DEFAULT_CURRENCIES.get(currency_code.upper())
        if not currency_obj:
            raise InvalidCurrencyError(f"Unsupported currency code: {currency_code}")



        account_number = f"{user.id}{datetime.utcnow().timestamp():.0f}"[-10:]


        if balance_limit is not None and balance_limit < 0:
            raise InvalidLimitValueError("Balance limit cannot be negative.")
        if daily_debit_limit is not None and daily_debit_limit < 0:
            raise InvalidLimitValueError("Daily debit limit cannot be negative.")

        account = Account(
            user_id=user.id,
            account_number=account_number,
            type=account_type.lower(),
            currency=currency_obj,
            balance=0.0,

            balance_limit=balance_limit if balance_limit is not None else Account.model_fields['balance_limit'].default,
            daily_debit_limit=daily_debit_limit if daily_debit_limit is not None else Account.model_fields['daily_debit_limit'].default,
            account_status=AccountStatus()
        )
        await account.create()





        return account

    async def get_account_by_id(self, account_id: PydanticObjectId, requesting_user: User, fetch_links: bool = True) -> Account:
        """Gets a single account by its ID, checking authorization."""
        account = await self._get_account(str(account_id), fetch_links=fetch_links)
        if not account.user_id or account.user_id.id != requesting_user.id and not requesting_user.is_admin:
             raise UnauthorizedError("You do not have permission to view this account.")
        return account

    async def get_account_by_number(self, account_number: str, requesting_user: User, fetch_links: bool = True) -> Account:
        """Gets a single account by its number, checking authorization."""
        account = await self._get_account(account_number, fetch_links=fetch_links)

        if not isinstance(account.user_id, User):
             await account.fetch_link(Account.user_id)
        if not account.user_id or account.user_id.id != requesting_user.id and not requesting_user.is_admin:
            raise UnauthorizedError("You do not have permission to view this account.")
        return account

    async def get_user_accounts(self, user_id: PydanticObjectId) -> List[Account]:
        """Gets all accounts belonging to a specific user."""

        accounts = await Account.find(Account.user_id.id == user_id, fetch_links=True).to_list()




        return accounts

    async def update_account_limits(self, account_id: PydanticObjectId, requesting_user: User, balance_limit: Optional[float], daily_debit_limit: Optional[float]) -> Account:
        """Updates the balance and/or daily debit limit of an account."""
        account = await self.get_account_by_id(account_id, requesting_user)


        if account.user_id.id != requesting_user.id and not requesting_user.is_admin:
            raise UnauthorizedError("Only the account owner or an admin can change limits.")

        updated = False
        if balance_limit is not None:
            if balance_limit < 0:
                raise InvalidLimitValueError("Balance limit cannot be negative.")
            account.balance_limit = balance_limit
            updated = True
        if daily_debit_limit is not None:
             if daily_debit_limit < 0:
                raise InvalidLimitValueError("Daily debit limit cannot be negative.")
             account.daily_debit_limit = daily_debit_limit
             updated = True

        if updated:
            account.updated = datetime.utcnow()
            await account.save()
        return account

    async def update_account_status(self, account_id: PydanticObjectId, requesting_user: User, status: str, description: Optional[str] = None) -> Account:
        """Updates the status of an account (Admin only)."""
        if not requesting_user.is_admin:
            raise UnauthorizedError("Only administrators can change account status.")

        if status.lower() not in ALLOWED_STATUSES:
             raise ValueError(f"Status must be one of: {', '.join(ALLOWED_STATUSES)}")

        account = await self._get_account(str(account_id), fetch_links=False)

        account.account_status.status = status.lower()
        account.account_status.description = description if description is not None else ""
        account.updated = datetime.utcnow()
        await account.save()
        return account

    async def get_account_status(self, account_id: PydanticObjectId, requesting_user: User) -> AccountStatus:
         """Gets the status of an account."""

         account = await self.get_account_by_id(account_id, requesting_user)
         return account.account_status

    async def delete_account(self, account_id: PydanticObjectId, requesting_user: User) -> bool:
        """Deletes an account (owner or admin only)."""
        account = await self.get_account_by_id(account_id, requesting_user)


        if account.balance != 0.0:
            raise AccountStatusError(
                account_id=str(account.id),
                operation="delete",
                status=account.account_status.status,
                reason=f"Account balance ({account.balance} {account.currency.code}) is not zero."
            )



        delete_result = await account.delete()
        return delete_result.deleted_count > 0



    async def check_daily_limit(self, account: Account, amount: float):
        """Checks if the debit amount exceeds the daily limit."""
        today = datetime.utcnow().date()

        if account.last_debit_date != today:


            account.daily_debit_total = 0.0


        if account.daily_debit_limit is not None:
            if account.daily_debit_total + amount > account.daily_debit_limit:
                raise DailyLimitExceededError(
                    account_id=str(account.id),
                    attempted=amount,
                    limit=account.daily_debit_limit,
                    daily_total=account.daily_debit_total
                )

    async def check_debit_conditions(self, account: Account, amount: float):
        """Performs all checks required before debiting an account."""

        if account.account_status.status != "unrestricted":
            raise AccountStatusError(
                account_id=str(account.id),
                operation="debit",
                status=account.account_status.status,
                reason=account.account_status.description
            )


        if account.balance < amount:
            raise InsufficientFundsError(
                account_id=str(account.id),
                needed=amount,
                available=account.balance
            )


        await self.check_daily_limit(account, amount)

    async def check_credit_conditions(self, account: Account, amount: float):
        """Performs all checks required before crediting an account."""

        if account.account_status.status == "frozen":
             raise AccountStatusError(
                 account_id=str(account.id),
                 operation="credit",
                 status=account.account_status.status,
                 reason="Account is frozen and cannot receive funds."
             )


        if account.balance_limit is not None:
            if account.balance + amount > account.balance_limit:
                raise BalanceLimitExceededError(
                    account_id=str(account.id),
                    attempted=amount,
                    limit=account.balance_limit,
                    current_balance=account.balance
                )



    async def perform_debit(self, account: Account, amount: float, session=None):
        """
        Decrements balance and updates daily debit tracking.
        Assumes checks have passed. MUST be called within a transaction context.
        """
        today = datetime.utcnow().date()

        if account.last_debit_date != today:
            account.daily_debit_total = 0.0

        account.balance -= amount
        account.daily_debit_total += amount
        account.last_debit_date = today
        account.updated = datetime.utcnow()



    async def perform_credit(self, account: Account, amount: float, session=None):
        """
        Increments balance.
        Assumes checks have passed. MUST be called within a transaction context.
        """
        account.balance += amount
        account.updated = datetime.utcnow()

