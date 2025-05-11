# app/services/account.py
from beanie import PydanticObjectId, Link, WriteRules
from beanie.exceptions import DocumentNotFound
from typing import List, Optional
from datetime import datetime, date

from app.core.config import settings # Import settings
from app.schemas.account import Account, Currency, AccountStatus
from app.schemas.user import User
from app.exceptions.account import (
    AccountNotFoundError, InsufficientFundsError, DailyLimitExceededError,
    BalanceLimitExceededError, AccountStatusError, InvalidAccountTypeError,
    InvalidCurrencyError, InvalidLimitValueError
)
from app.exceptions.user import UnauthorizedError
# Assuming DatabaseUnavailableError is in app.exceptions.base or app.exceptions.database
from app.exceptions.base import DatabaseUnavailableError # Or the correct path


ALLOWED_ACCOUNT_TYPES = ["savings", "current"]
ALLOWED_STATUSES = ["unrestricted", "restricted", "frozen"]
DEFAULT_CURRENCIES = {
    "NGN": Currency(name="Nigerian Naira", code="NGN", symbol="₦"),
    "USD": Currency(name="US Dollar", code="USD", symbol="$"),
}

class AccountService:

    async def _get_account(self, identifier: str, fetch_links: bool = False) -> Account:
        if not settings.MONGODB_AVAILABLE:
            raise DatabaseUnavailableError(db_name="MongoDB", operation=f"get account '{identifier}'")

        try:
            account = await Account.get(PydanticObjectId(identifier), fetch_links=fetch_links)
            if account:
                if fetch_links and isinstance(account.user_id, Link) and not account.user_id.is_fetched:
                    await account.fetch_link(Account.user_id)
                return account
        except (ValueError, TypeError, DocumentNotFound): # PydanticObjectId conversion or Beanie not found
            pass # Fall through to find by account number

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
        if not settings.MONGODB_AVAILABLE:
            raise DatabaseUnavailableError(db_name="MongoDB", operation="create account")

        if account_type.lower() not in ALLOWED_ACCOUNT_TYPES:
            raise InvalidAccountTypeError(invalid_type=account_type, allowed_types=ALLOWED_ACCOUNT_TYPES)

        currency_obj = DEFAULT_CURRENCIES.get(currency_code.upper())
        if not currency_obj:
            raise InvalidCurrencyError(f"Unsupported currency code: {currency_code}")

        # Generate account number - ensure User object is valid if MongoDB was down during its fetch
        if not user or not user.id:
             # This implies user object might be incomplete if fetched when DB was down
            raise ValueError("Valid user object with an ID is required to create an account.")
        account_number = f"{str(user.id)}{datetime.utcnow().timestamp():.0f}"[-10:]


        if balance_limit is not None and balance_limit < 0:
            raise InvalidLimitValueError("Balance limit cannot be negative.")
        if daily_debit_limit is not None and daily_debit_limit < 0:
            raise InvalidLimitValueError("Daily debit limit cannot be negative.")

        account = Account(
            user_id=user.id, # type: ignore
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
        # _get_account already checks MONGODB_AVAILABLE
        account = await self._get_account(str(account_id), fetch_links=fetch_links)
        # Ensure user_id is fetched for authorization
        if isinstance(account.user_id, Link) and not account.user_id.is_fetched:
             if not settings.MONGODB_AVAILABLE: # Cannot fetch link if DB is down
                 raise DatabaseUnavailableError(db_name="MongoDB", operation="fetch linked user for authorization")
             await account.fetch_link(Account.user_id)

        if not account.user_id or (account.user_id.id != requesting_user.id and not requesting_user.is_admin): # type: ignore
            raise UnauthorizedError("You do not have permission to view this account.")
        return account

    async def get_account_by_number(self, account_number: str, requesting_user: User, fetch_links: bool = True) -> Account:
        # _get_account already checks MONGODB_AVAILABLE
        account = await self._get_account(account_number, fetch_links=fetch_links)
        # Ensure user_id is fetched for authorization
        if isinstance(account.user_id, Link) and not account.user_id.is_fetched:
            if not settings.MONGODB_AVAILABLE:
                raise DatabaseUnavailableError(db_name="MongoDB", operation="fetch linked user for authorization")
            await account.fetch_link(Account.user_id)

        if not account.user_id or (account.user_id.id != requesting_user.id and not requesting_user.is_admin): # type: ignore
            raise UnauthorizedError("You do not have permission to view this account.")
        return account

    async def get_user_accounts(self, user_id: PydanticObjectId) -> List[Account]:
        if not settings.MONGODB_AVAILABLE:
            # Or return empty list with a warning
            # print(f"WARNING: MongoDB not available. Cannot get accounts for user {user_id}.")
            # return []
            raise DatabaseUnavailableError(db_name="MongoDB", operation=f"get accounts for user {user_id}")

        accounts = await Account.find(Account.user_id.id == user_id, fetch_links=True).to_list() # type: ignore
        return accounts

    async def update_account_limits(self, account_id: PydanticObjectId, requesting_user: User, balance_limit: Optional[float], daily_debit_limit: Optional[float]) -> Account:
        if not settings.MONGODB_AVAILABLE:
            raise DatabaseUnavailableError(db_name="MongoDB", operation=f"update limits for account {account_id}")
        
        account = await self.get_account_by_id(account_id, requesting_user) # Handles its own DB check via _get_account

        # Authorization check (already partially in get_account_by_id, but more specific here)
        # Ensure account.user_id is the User object or Link is fetched.
        user_is_owner = False
        if isinstance(account.user_id, User): # If already a fetched User object
            user_is_owner = account.user_id.id == requesting_user.id
        elif isinstance(account.user_id, Link) and account.user_id.ref: # If it's a Link with an ID
            user_is_owner = account.user_id.ref.id == requesting_user.id # type: ignore

        if not user_is_owner and not requesting_user.is_admin:
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
        if not settings.MONGODB_AVAILABLE:
            raise DatabaseUnavailableError(db_name="MongoDB", operation=f"update status for account {account_id}")

        if not requesting_user.is_admin:
            raise UnauthorizedError("Only administrators can change account status.")

        if status.lower() not in ALLOWED_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(ALLOWED_STATUSES)}")

        account = await self._get_account(str(account_id), fetch_links=False) # No need to fetch links for this operation

        account.account_status.status = status.lower()
        account.account_status.description = description if description is not None else ""
        account.updated = datetime.utcnow()
        await account.save()
        return account

    async def get_account_status(self, account_id: PydanticObjectId, requesting_user: User) -> AccountStatus:
        # Relies on get_account_by_id, which checks DB availability
        account = await self.get_account_by_id(account_id, requesting_user)
        return account.account_status

    async def delete_account(self, account_id: PydanticObjectId, requesting_user: User) -> bool:
        if not settings.MONGODB_AVAILABLE:
            raise DatabaseUnavailableError(db_name="MongoDB", operation=f"delete account {account_id}")
        
        account = await self.get_account_by_id(account_id, requesting_user) # Handles DB check & auth

        if account.balance != 0.0:
            raise AccountStatusError(
                account_id=str(account.id), # type: ignore
                operation="delete",
                status=account.account_status.status,
                reason=f"Account balance ({account.balance} {account.currency.code}) is not zero."
            )

        delete_result = await account.delete()
        return delete_result.deleted_count > 0 if delete_result else False


    # Methods like check_daily_limit, check_debit_conditions, check_credit_conditions
    # operate on an Account object that should have been fetched. If MongoDB was down,
    # fetching the account would have failed earlier. So, no explicit DB check needed here,
    # assuming 'account' argument is valid.

    async def check_daily_limit(self, account: Account, amount: float):
        today = datetime.utcnow().date()
        if account.last_debit_date != today:
            account.daily_debit_total = 0.0 # This change would need saving if it were persistent across calls
                                          # but it's usually checked then updated in perform_debit

        if account.daily_debit_limit is not None:
            if account.daily_debit_total + amount > account.daily_debit_limit:
                raise DailyLimitExceededError(
                    account_id=str(account.id), # type: ignore
                    attempted=amount,
                    limit=account.daily_debit_limit,
                    daily_total=account.daily_debit_total
                )

    async def check_debit_conditions(self, account: Account, amount: float):
        if account.account_status.status != "unrestricted":
            raise AccountStatusError(
                account_id=str(account.id), # type: ignore
                operation="debit",
                status=account.account_status.status,
                reason=account.account_status.description
            )
        if account.balance < amount:
            raise InsufficientFundsError(
                account_id=str(account.id), # type: ignore
                needed=amount,
                available=account.balance
            )
        await self.check_daily_limit(account, amount)

    async def check_credit_conditions(self, account: Account, amount: float):
        if account.account_status.status == "frozen":
            raise AccountStatusError(
                account_id=str(account.id), # type: ignore
                operation="credit",
                status=account.account_status.status,
                reason="Account is frozen and cannot receive funds."
            )
        if account.balance_limit is not None:
            if account.balance + amount > account.balance_limit:
                raise BalanceLimitExceededError(
                    account_id=str(account.id), # type: ignore
                    attempted=amount,
                    limit=account.balance_limit,
                    current_balance=account.balance
                )

    async def perform_debit(self, account: Account, amount: float, session=None):
        if not settings.MONGODB_AVAILABLE: # Should not reach here if checks were done, but as safety
            raise DatabaseUnavailableError(db_name="MongoDB", operation="perform debit")
        
        today = datetime.utcnow().date()
        if account.last_debit_date != today:
            account.daily_debit_total = 0.0 # Reset for the new day

        account.balance -= amount
        account.daily_debit_total += amount
        account.last_debit_date = today
        account.updated = datetime.utcnow()
        # Saving is usually done by the calling function (e.g., transfer_funds) within the session

    async def perform_credit(self, account: Account, amount: float, session=None):
        if not settings.MONGODB_AVAILABLE: # Safety check
            raise DatabaseUnavailableError(db_name="MongoDB", operation="perform credit")

        account.balance += amount
        account.updated = datetime.utcnow()
        # Saving is usually done by the calling function