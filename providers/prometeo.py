import os
import httpx
from .base import BankProvider, Account, Transaction
from datetime import datetime


class PrometeoProvider(BankProvider):
    BASE_URL = "https://banking.sandbox.prometeoapi.com"

    def __init__(self):
        self.api_key = os.getenv("PROMETEO_API_KEY")
        self.session_key: str | None = None
        self._client = httpx.AsyncClient(base_url=self.BASE_URL, timeout=30)
        self._client.headers["X-API-Key"] = self.api_key or ""

    async def authenticate(self, username: str = "", password: str = "", provider: str = "interbank_pers_pe") -> bool:
        resp = await self._client.post("/login/", data={
            "provider": provider,
            "username": username,
            "password": password,
        })
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "logged_in":
                self.session_key = data["key"]
                return True
            if data.get("status") == "interaction_required":
                return False
        return False

    async def submit_otp(self, otp: str) -> bool:
        resp = await self._client.post("/login/", data={
            "key": self.session_key,
            "otp": otp,
        })
        if resp.status_code == 200 and resp.json().get("status") == "logged_in":
            self.session_key = resp.json()["key"]
            return True
        return False

    async def get_accounts(self) -> list[Account]:
        resp = await self._client.get("/account/", params={"key": self.session_key})
        resp.raise_for_status()
        return [
            Account(
                id=a["number"],
                name=a.get("name", "Interbank Account"),
                bank="Interbank",
                currency=a.get("currency", "PEN"),
                balance=float(a.get("balance", 0)),
            )
            for a in resp.json().get("accounts", [])
        ]

    async def get_transactions(self, account_id: str, from_date: str, to_date: str) -> list[Transaction]:
        resp = await self._client.get(f"/account/{account_id}/movement/", params={
            "key": self.session_key,
            "date_start": from_date,
            "date_end": to_date,
        })
        resp.raise_for_status()
        return [
            Transaction(
                id=t.get("id", f"{account_id}_{i}"),
                date=datetime.strptime(t["date"], "%d/%m/%Y"),
                description=t.get("detail", ""),
                amount=float(t.get("debit", 0) or 0) * -1 if t.get("debit") else float(t.get("credit", 0)),
                currency=t.get("currency", "PEN"),
                category=None,
                account_id=account_id,
            )
            for i, t in enumerate(resp.json().get("movements", []))
        ]

    async def logout(self):
        if self.session_key:
            await self._client.get("/logout/", params={"key": self.session_key})
