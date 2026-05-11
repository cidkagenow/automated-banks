# Automated Banks

Automated bank balance extraction via iPhone Mirroring on macOS. A vision-driven agent controls your iPhone through macOS's iPhone Mirroring, navigates bank apps, logs in, and extracts all account balances — no jailbreak, no API, no scraping.

## How It Works

1. **iPhone Mirroring** renders your iPhone screen as a macOS window
2. **Quartz CGEvents** send synthetic taps, swipes, and keystrokes to the mirrored screen
3. **Gemini Vision AI** classifies each screenshot against a state machine to decide what to do next
4. A **state machine per bank** defines every screen the agent might encounter and the action to take
5. Balances are extracted as structured JSON and appended to a CSV on your Desktop

See [WORKFLOW.md](WORKFLOW.md) for the full pipeline and [STATE_MACHINES.md](STATE_MACHINES.md) for per-bank state definitions.

## Supported Banks

| Bank | Country | Currency | Auth Method |
|------|---------|----------|-------------|
| Maybank (MAE) | Malaysia | MYR | 6-digit PIN keypad |
| Interbank | Peru | PEN/USD | Password field |

## Requirements

- macOS Sequoia 15+ with iPhone Mirroring
- iPhone paired and set up for mirroring
- Python 3.11+
- Gemini API key ([get one here](https://aistudio.google.com/apikey))
- macOS permissions: Accessibility, Screen Recording, Automation

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file:

```
GEMINI_API_KEY=your-gemini-api-key
MAYBANK_APP_PASSWORD=123456
INTERBANK_APP_PASSWORD=your-password
MAC_LOGIN_PASSWORD=your-mac-password
```

## Usage

```bash
# Read one bank
python run.py agent maybank
python run.py agent interbank

# Read all banks, append to ~/Desktop/bank_balances.csv
python run.py all

# Check iPhone Mirroring window detection
python run.py probe
```

## Output

Each run appends rows to `~/Desktop/bank_balances.csv`:

```
timestamp,bank,account,amount,currency,kind
2026-05-11T16:12:04Z,maybank,Savings Account-i,3.22,MYR,
2026-05-11T16:12:04Z,interbank,Cuenta Simple Soles,10.25,PEN,debit
2026-05-11T16:12:04Z,interbank,dollars,0.56,USD,debit
...
```

JSON snapshots are also saved to `data/snapshots.json`.

## Project Structure

```
automated-banks/
├── run.py                 # CLI entry point
├── agent/
│   ├── actions.py         # Synthetic input (taps, swipes, scroll, keyboard)
│   ├── runner.py          # Main loop: screenshot -> classify -> act -> repeat
│   ├── screenshot.py      # Capture iPhone Mirroring window
│   ├── states.py          # State machines for each bank
│   ├── storage.py         # JSON snapshot persistence
│   ├── vision.py          # Gemini AI classification and extraction
│   └── window.py          # Locate and focus iPhone Mirroring window
├── data/
│   ├── screenshots/       # Debug screenshots per run
│   └── snapshots.json     # Historical balance snapshots
├── requirements.txt
└── .env                   # Secrets (not committed)
```

## Adding a New Bank

1. Add a new state machine dict in `agent/states.py` following the existing pattern
2. Define states for: loading, login, navigation, and the final balance screen
3. Use `tap_norm` with normalized (0-1) coordinates so it works across iPhone models
4. Add the bank to the `BANKS` dict at the bottom of the file
5. Add any new password env vars to `ALLOWED_PASSWORD_KEYS` in `agent/actions.py`

## Key Technical Details

- **Taps**: Quartz CGEvents with explicit click-count — more reliable than pyautogui in iPhone Mirroring
- **Scrolling**: Trackpad-style phased scroll wheel events (began/changed/ended) — the only scroll method iPhone Mirroring accepts
- **Keyboard**: AppleScript `System Events` keystrokes — required because macOS Secure Input Mode blocks pyautogui in password fields
- **App launching**: Spotlight search via keyboard (Cmd+3, type name, Enter) — synthetic clicks don't work on the iOS home screen
- **Coordinates**: All normalized (0-1) so they adapt to different iPhone screen sizes
