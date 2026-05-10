# Bank Tracker — AI Phone Agent

## Project Goal
Build an AI agent that controls the user's iPhone (mirrored to Mac) to automate banking tasks — reading balances, transactions, and eventually automating transfers. The user has two bank accounts:
- **Maybank** (Malaysia)
- **Interbank** (Peru)

Both apps are installed on the user's iPhone.

## Why This Approach
We explored multiple approaches before landing on phone automation:

### Ruled Out
- **Finverse** (Maybank aggregator) — B2B only, requires business agreement, not free for personal use
- **Prometeo** (Interbank aggregator) — B2B only, sandbox is free but production requires sales contact and fees
- **Interbank Open Banking API** (`portal.api.interbank.pe`) — free sandbox exists but production access likely requires business relationship
- **Maybank MConnect API** — merchant/payment focused, not account data access
- **Bank of China Malaysia** — no API, no aggregator support, hardware e-token for web banking
- **Web scraping Maybank2u** — Secure2u mobile 2FA, security image verification, anti-bot detection, violates Malaysia Computer Crimes Act
- **Web scraping Interbank** — SMS-based 2FA (Clave SMS), violates Peru Ley 30096
- **Statement CSV/PDF parsing** — user wants a more automated solution
- **All aggregators (Plaid, SaltEdge, Tink, Belvo, Brankas, etc.)** — none support both Malaysian and Peruvian banks for free personal use

### Chosen Approach: iPhone Mirroring + AI Vision Agent
Free stack using:
1. **iPhone Mirroring** (built into macOS Sequoia+) — mirrors phone to Mac
2. **`screencapture`** (macOS built-in) — screenshots the mirrored window
3. **PyAutoGUI** — programmatic mouse/keyboard control on the mirrored window
4. **AI vision** (Claude API or Ollama for local/free) — analyzes screenshots, decides actions
5. **Loop**: screenshot → AI decides → PyAutoGUI acts → repeat

## Current State
- A FastAPI + Jinja2 dashboard skeleton exists in this repo at `api/server.py` and `dashboard/index.html`
- Provider abstractions exist for Finverse and Prometeo but are **NOT useful** — to be replaced with the phone agent approach
- Virtual environment is set up with dependencies installed (httpx, fastapi, uvicorn, jinja2, rich, python-dotenv)
- The dashboard runs on port **8050** (`python run.py`)

## What Needs To Be Built Next
1. **Verify iPhone Mirroring works** on the user's Mac (requires macOS Sequoia+)
2. **Window detection** — find and locate the iPhone Mirroring window on screen
3. **Screenshot module** — capture the mirrored iPhone window
4. **AI vision integration** — send screenshots to Claude API or local Ollama to interpret the screen
5. **Action executor** — translate AI decisions into PyAutoGUI clicks/taps on the mirrored window
6. **Agent loop** — screenshot → analyze → act → repeat
7. **Banking flows** — specific routines for:
   - Opening Maybank/Interbank apps
   - Logging in (handle biometrics prompt — user confirms Face ID on phone)
   - Reading account balances
   - Reading transaction history
   - (Later) Initiating transfers with manual confirmation step
8. **Dashboard integration** — store scraped data and display in the existing web dashboard
9. **Add PyAutoGUI and Pillow to requirements.txt**

## Safety Rules
- **Start read-only** — only read balances and transactions first
- **Manual confirmation required** before any money transfer
- **Keep everything local** — no sending bank data to external services (use Ollama if avoiding Claude API costs)
- Be aware of risks: app UI changes can break automation, banks may detect bot behavior

## Tech Stack
- Python 3.13
- FastAPI + Jinja2 (dashboard)
- PyAutoGUI (mouse/keyboard automation)
- Pillow (screenshots)
- Claude API or Ollama (AI vision)
- macOS iPhone Mirroring

## User Context
- User is a programmer
- Has an iPhone with Maybank and Interbank apps installed
- Uses a Mac (macOS, Apple Silicon)
- Located in Malaysia, also has banking in Peru
- Prefers free/no-cost solutions
- Wants maximum automation with safety guardrails for transactions

## File Structure
```
bank-tracker/
├── CLAUDE.md              # This file
├── .env.example           # API keys template
├── .env                   # Local API keys (gitignored)
├── .gitignore
├── requirements.txt       # Python dependencies
├── run.py                 # Entry point (uvicorn on port 8050)
├── providers/
│   ├── base.py            # Account & Transaction dataclasses
│   ├── finverse.py        # (TO BE REPLACED) Finverse provider
│   └── prometeo.py        # (TO BE REPLACED) Prometeo provider
├── api/
│   └── server.py          # FastAPI routes + dashboard
└── dashboard/
    └── index.html         # Web dashboard (dark theme)
```
