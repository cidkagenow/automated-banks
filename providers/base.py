from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Account:
    id: str
    name: str
    bank: str
    currency: str
    balance: float


@dataclass
class Transaction:
    id: str
    date: datetime
    description: str
    amount: float
    currency: str
    category: str | None = None
    account_id: str | None = None


class BankProvider(ABC):
    @abstractmethod
    async def authenticate(self) -> bool:
        pass

    @abstractmethod
    async def get_accounts(self) -> list[Account]:
        pass

    @abstractmethod
    async def get_transactions(self, account_id: str, from_date: str, to_date: str) -> list[Transaction]:
        pass
