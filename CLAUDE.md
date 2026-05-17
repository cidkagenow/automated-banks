# automated-banks

Automates bank balance extraction from Maybank (MAE) and Interbank Peru via iPhone Mirroring on macOS.

## Setup

1. Clone this repo
2. Create venv and install deps:
   ```
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your credentials
4. Open iPhone Mirroring on your Mac, lock your iPhone so it connects

## Usage

In Claude Code, run:
```
/project:bank-balances
```

Claude will drive your phone via iPhone Mirroring — taking screenshots, reading them, and tapping through each bank app to extract balances. Results are saved to `~/Desktop/bank_balances.csv`.

## Required .env keys (for the slash command)

- `MAC_LOGIN_PASSWORD` — your Mac login password (to unlock iPhone Mirroring)
- `MAYBANK_APP_PASSWORD` — 6-digit MAE app PIN
- `INTERBANK_APP_PASSWORD` — Interbank app password
