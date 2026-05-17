# Bank Balances — iPhone Mirroring Agent

Extract balances from Maybank and Interbank via iPhone Mirroring. You (Claude) are the vision AI — take screenshots, look at them, and drive the phone with taps.

## Prerequisites Check

Before starting, verify ALL of these. If any fail, stop and tell the user what to fix.

1. **iPhone Mirroring running:** Run this to check:
   ```
   .venv/bin/python -c "from agent import window; b = window.find(); print(f'OK: {b.width}x{b.height} id={b.window_id}')"
   ```
   If it fails, tell user to open iPhone Mirroring and lock their phone.

2. **Env vars set:** Check `.env` has these keys (don't print values):
   - `MAC_LOGIN_PASSWORD`
   - `MAYBANK_APP_PASSWORD`
   - `INTERBANK_APP_PASSWORD`

3. **Venv exists:** Check `.venv/bin/python` exists and can import `agent.window`.

## How to Drive the Phone

You are the vision AI. Repeat this loop: **screenshot → view → decide → act**.

### Screenshot & View
```bash
screencapture -x -o -l <WINDOW_ID> /tmp/iphone_now.png
```
Then use the Read tool on `/tmp/iphone_now.png` to see the screen.

### Execute Actions
Always use the project venv and load dotenv:
```python
.venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv()
from agent import window, actions
from agent.screenshot import size
import time

b = window.find()
sz = size('/tmp/iphone_now.png')
coord = actions.Coord(b, sz[0], sz[1])

# Then do ONE of:
# Tap at normalized position:
actions.tap(coord, int(sz[0] * X_NORM), int(sz[1] * Y_NORM))
# Type password:
actions.type_password('ENV_KEY_NAME')
# Press key:
actions.press('enter')
# Scroll down:
actions.scroll_down(coord, 400)
# Go home:
actions.go_home()
# Launch app via Spotlight:
actions.launch('AppName')
# Close front app:
actions.close_front_app(b)
"
```

### IPM Lock Screen
The lock screen blocks Quartz/pyautogui clicks. Use AppleScript:
```bash
osascript -e 'tell application "System Events" to tell process "iPhone Mirroring" to click text field 1 of group 1 of window 1'
```
Then type password + press enter:
```python
actions.type_password('MAC_LOGIN_PASSWORD')
actions.press('enter')
```

## Flow: Maybank

1. Close any front app: `actions.close_front_app(b)`
2. Launch: `actions.launch('MAE')`
3. Wait 3s, screenshot. You should see the MAE home screen (yellow/black, "Hello" greeting, balance visible).
4. If already showing Accounts page with balances → extract and skip to step 7.
5. Tap "Accounts" tab (bottom bar, second from left): `x=0.30, y=0.93`
6. PIN prompt appears (yellow keypad, "6-digit MAE app PIN"). Tap digits using this layout:
   ```
   1: [0.25, 0.69]  2: [0.50, 0.69]  3: [0.75, 0.69]
   4: [0.25, 0.78]  5: [0.50, 0.78]  6: [0.75, 0.78]
   7: [0.25, 0.87]  8: [0.50, 0.87]  9: [0.75, 0.87]
                     0: [0.50, 0.93]
   Submit (checkmark): [0.75, 0.93]
   ```
   Read each digit from `MAYBANK_APP_PASSWORD` env var and tap the corresponding position. Tap submit after all digits.
7. Accounts page shows cards with account names + "RM X.XX" balances. Read all visible accounts.

## Flow: Interbank

1. Go home: `actions.go_home()`, wait 1.5s
2. Close front app: `actions.close_front_app(b)`, wait 1.5s
3. Launch: `actions.launch('Interbank')`
4. Wait 4s, screenshot. You should see "Hola <name>" with password field and "Ingresar" button.
5. If you see a sub-page (back arrow at top-left, NOT the main login), tap back: `x=0.084, y=0.097`
6. If you see a marketing modal or "Entendido" button, tap it: `x=0.50, y=0.65`
7. If you see session expired ("Lo sentimos" / "Tu sesión ha expirado"), tap Aceptar: `x=0.50, y=0.68`
8. On main login: tap password field `x=0.50, y=0.573`, type password `INTERBANK_APP_PASSWORD`, tap Ingresar `x=0.50, y=0.649`
9. Wait 5s, screenshot. Should show "Productos" page with account list.
10. Read all visible accounts (name + S/ or $ amount).
11. Scroll down (`scroll_down(coord, 400)`) and screenshot again to catch any accounts below the fold.
12. Read remaining accounts.

## Save Results

Write all balances to `~/Desktop/bank_balances.csv` (append mode). Columns:
```
timestamp, bank, account, amount, currency, kind
```

- `timestamp`: UTC ISO format
- `bank`: "maybank" or "interbank"
- `currency`: "MYR" for Maybank, "PEN" for S/ amounts, "USD" for $ amounts
- `kind`: "debit" for savings/checking (Saldo disponible), "credit" for credit cards (Línea disponible)

If the file doesn't exist, write the header row first.

## Error Handling

- **"iPhone in Use"**: Tell user to lock their phone and try again.
- **"iPhone Mirroring Is Locked"**: Use the AppleScript unlock method above.
- **"Connecting to..."**: Wait 3 seconds and screenshot again.
- **PIN/password rejected**: Do NOT retry — tell user to check their .env credentials.
- **Lockout ("límite máximo de intentos")**: Stop immediately. Tell user their account is locked.
- **App not found in Spotlight**: Go home, wait 2s, try launching again once.
- **Unexpected screen**: Take a screenshot, show it to the user, and ask what to do.

## After Completion

Print a summary table of all balances found and the path to the CSV file.
