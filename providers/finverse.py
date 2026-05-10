import os
import httpx
from .base import BankProvider, Account, Transaction
from datetime import datetime


class FinverseProvider(BankProvider):
    BASE_URL = "https://api.finverse.com/v1"

    def __init__(self):
        self.client_id = os.getenv("FINVERSE_CLIENT_ID")
        self.client_secret = os.getenv("FINVERSE_CLIENT_SECRET")
        self.redirect_uri = os.getenv("FINVERSE_REDIRECT_URI")
        self.access_token: str | None = None
        self._client = httpx.AsyncClient(base_url=self.BASE_URL, timeout=30)

    async def authenticate(self) -> bool:
        resp = await self._client.post("/auth/token", json={
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
        })
        if resp.status_code == 200:
            self.access_token = resp.json()["access_token"]
            self._client.headers["Authorization"] = f"Bearer {self.access_token}"
            return True
        return False

    def get_login_url(self) -> str:
        return (
            f"{self.BASE_URL}/auth/authorize"
            f"?client_id={self.client_id}"
            f"&redirect_uri={self.redirect_uri}"
            f"&response_type=code"
            f"&institution_id=maybank_my"
        )

    async def exchange_code(self, code: str) -> bool:
        resp = await self._client.post("/auth/token", json={
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
        })
        if resp.status_code == 200:
            data = resp.json()
            self.access_token = data["access_token"]
            self._client.headers["Authorization"] = f"Bearer {self.access_token}"
            return True
        return False

    async def get_accounts(self) -> list[Account]:
        resp = await self._client.get("/accounts")
        resp.raise_for_status()
        return [
            Account(
                id=a["account_id"],
                name=a.get("account_name", "Maybank Account"),
                bank="Maybank",
                currency=a.get("currency", "MYR"),
                balance=float(a.get("balance", {}).get("current", 0)),
            )
            for a in resp.json().get("accounts", [])
        ]

    async def get_transactions(self, account_id: str, from_date: str, to_date: str) -> list[Transaction]:
        resp = await self._client.get(f"/accounts/{account_id}/transactions", params={
            "from_date": from_date,
            "to_date": to_date,
        })
        resp.raise_for_status()
        return [
            Transaction(
                id=t["transaction_id"],
                date=datetime.fromisoformat(t["date"]),
                description=t.get("description", ""),
                amount=float(t.get("amount", 0)),
                currency=t.get("currency", "MYR"),
                category=t.get("category"),
                account_id=account_id,
            )
            for t in resp.json().get("transactions", [])
        ]
