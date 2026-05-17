# automated-banks

Automates bank balance extraction from Maybank (MAE) and Interbank Peru.

Two approaches:
- **iPhone Mirroring** — Claude Code drives the phone via `/project:bank-balances`
- **Web scraper** — Playwright automates Interbank's web portal via `python run.py web interbank`

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in your credentials
```

For iPhone Mirroring: open iPhone Mirroring on your Mac, lock your phone.

## Usage

```bash
# Claude Code slash command — drives both banks via iPhone Mirroring
/project:bank-balances

# Web scraper — Interbank only
python run.py web interbank
python run.py web interbank --dry-run   # fill form without submitting

# Debug — check iPhone Mirroring window detection
python run.py probe
```

## Project structure

```
agent/actions.py      # Synthetic input (taps, swipes, scroll, keyboard)
agent/screenshot.py   # Capture iPhone Mirroring window
agent/storage.py      # JSON snapshot persistence
agent/window.py       # Locate and focus iPhone Mirroring window
web/browser.py        # Playwright browser lifecycle
web/interbank.py      # Interbank web portal automation
web/otp.py            # Yahoo IMAP OTP reader
run.py                # CLI entry point
.claude/commands/bank-balances.md  # Slash command for Claude Code
```
