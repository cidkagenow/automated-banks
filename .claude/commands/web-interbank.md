# Web Interbank — Playwright Automation

Extract balances and transaction statements from Interbank Peru's web portal using Playwright browser automation.

## Prerequisites Check

Before starting, verify ALL of these. If any fail, stop and tell the user what to fix.

1. **Venv exists:** Check `.venv/bin/python` exists and can import `web.interbank`.
2. **Playwright installed:** `.venv/bin/python -m playwright install chromium` if needed.
3. **Env vars set:** Check `.env` has these keys (don't print values):
   - `INTERBANK_DNI` — DNI number for web login
   - `INTERBANK_WEB_PASSWORD` — web portal password (may differ from app password)
   - `YAHOO_EMAIL` — Yahoo email where OTP codes are sent
   - `YAHOO_APP_PASSWORD` — Yahoo app password for IMAP access
   - `INTERBANK_WEB_ACCOUNTS` (optional) — comma-separated account names for statement extraction

## How to Run

Run from the project root:

### Dry run (recommended first time)
```bash
.venv/bin/python run.py web interbank --dry-run
```
This fills the login form but does NOT submit. A screenshot is saved showing the revealed password so the user can verify the virtual keyboard typed it correctly. **Always do a dry run first** to avoid account lockout from wrong passwords.

### Full run
```bash
.venv/bin/python run.py web interbank
```

## What It Does

1. **Opens Chrome** (headed, visible) with anti-bot stealth settings
2. **Navigates** to `https://bancaporinternet.interbank.pe/login`
3. **Fills DNI** via keyboard typing
4. **Fills password** via the on-screen virtual keyboard (the password field is readonly — only accepts virtual keyboard clicks). Handles shift key for uppercase letters.
5. **Reveals password** via eye icon and takes a screenshot for verification
6. **Submits** the login form
7. **Reads OTP** automatically from Yahoo Mail via IMAP (polls every 5s, max 90s)
8. **Enters OTP** and submits step 2
9. **Extracts balances** from the dashboard (regex parsing of page text)
10. **Extracts statements** for each account in `INTERBANK_WEB_ACCOUNTS` (clicks account card, reads transaction table)
11. **Returns JSON** with all data and saves to `data/snapshots.json`

## Important Warnings

- **Account lockout:** Interbank locks accounts after 3 failed password attempts for ~24 hours. Always dry-run first.
- **Virtual keyboard:** The password field uses a scrambled SVG virtual keyboard. Shift key is `div.special-key-cap-lock`, NOT a regular `<a class="key">`.
- **OTP timing:** The OTP email must arrive within 90 seconds. Make sure Yahoo IMAP access is working before attempting login.
- **Web password ≠ app password:** The Interbank web portal password ("clave web") may be different from the mobile app password.

## Troubleshooting

- **"networkidle timeout"**: Normal — the SPA keeps connections alive. Code uses `domcontentloaded` instead.
- **Modal blocking form**: The site shows "Hemos renovado tu Banca por Internet" overlays. Code auto-dismisses them.
- **Wrong password in screenshot**: Check `.env` — the virtual keyboard may have failed on shift key. Look at the `password-revealed` screenshot in `data/screenshots/`.
- **OTP not received**: Check Yahoo spam folder. Verify `YAHOO_APP_PASSWORD` is an app-specific password (not your Yahoo login password). Generate one at https://login.yahoo.com/account/security/app-passwords
- **"Lo sentimos" / rate limited**: Wait a few minutes and try again.

## Output

- JSON printed to stdout with `success`, `balances`, `statements`, `error`
- Snapshots saved to `data/snapshots.json`
- Debug screenshots saved to `data/screenshots/`
