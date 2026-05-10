from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json
import os

from providers.finverse import FinverseProvider
from providers.prometeo import PrometeoProvider
from providers.base import Account, Transaction

load_dotenv()

app = FastAPI(title="Bank Tracker")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "dashboard"))

finverse = FinverseProvider()
prometeo = PrometeoProvider()

all_accounts: list[Account] = []
all_transactions: list[Transaction] = []


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    totals = {}
    for acc in all_accounts:
        totals[acc.currency] = totals.get(acc.currency, 0) + acc.balance

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "accounts": all_accounts,
            "transactions": sorted(all_transactions, key=lambda t: t.date, reverse=True)[:50],
            "totals": totals,
        },
    )


@app.get("/connect/maybank")
async def connect_maybank():
    await finverse.authenticate()
    return RedirectResponse(finverse.get_login_url())


@app.get("/callback/finverse")
async def finverse_callback(code: str):
    await finverse.exchange_code(code)
    accounts = await finverse.get_accounts()
    all_accounts.extend(accounts)

    today = datetime.now().strftime("%Y-%m-%d")
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    for acc in accounts:
        txns = await finverse.get_transactions(acc.id, month_ago, today)
        all_transactions.extend(txns)

    return RedirectResponse("/")


@app.post("/connect/interbank")
async def connect_interbank(request: Request):
    form = await request.form()
    username = form.get("username", "")
    password = form.get("password", "")

    success = await prometeo.authenticate(username=username, password=password)
    if not success:
        return {"status": "otp_required", "message": "Check your phone for SMS code"}

    accounts = await prometeo.get_accounts()
    all_accounts.extend(accounts)

    today = datetime.now().strftime("%d/%m/%Y")
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%d/%m/%Y")
    for acc in accounts:
        txns = await prometeo.get_transactions(acc.id, month_ago, today)
        all_transactions.extend(txns)

    return RedirectResponse("/", status_code=303)


@app.post("/connect/interbank/otp")
async def interbank_otp(request: Request):
    form = await request.form()
    otp = form.get("otp", "")
    success = await prometeo.submit_otp(otp)
    if not success:
        return {"status": "error", "message": "Invalid OTP"}

    accounts = await prometeo.get_accounts()
    all_accounts.extend(accounts)

    today = datetime.now().strftime("%d/%m/%Y")
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%d/%m/%Y")
    for acc in accounts:
        txns = await prometeo.get_transactions(acc.id, month_ago, today)
        all_transactions.extend(txns)

    return RedirectResponse("/", status_code=303)


@app.get("/api/accounts")
async def api_accounts():
    return [
        {"id": a.id, "name": a.name, "bank": a.bank, "currency": a.currency, "balance": a.balance}
        for a in all_accounts
    ]


@app.get("/api/transactions")
async def api_transactions():
    return [
        {
            "id": t.id, "date": t.date.isoformat(), "description": t.description,
            "amount": t.amount, "currency": t.currency, "category": t.category,
        }
        for t in sorted(all_transactions, key=lambda t: t.date, reverse=True)
    ]
