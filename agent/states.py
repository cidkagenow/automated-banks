"""State machines for each bank.

Each bank is a dict with:
  states:    list of {name, desc, do} entries
  max_steps: hard ceiling on classifier loops before we give up

`do` is a tagged dict — the runner switches on `type`:
  {"type": "launch", "app": "Maybank"}
  {"type": "wait", "seconds": 2.0}
  {"type": "tap", "x": 326, "y": 825}
  {"type": "type_password", "key": "INTERBANK_APP_PASSWORD"}
  {"type": "press", "key": "enter"}
  {"type": "home"}
  {"type": "done", "extract": "<instruction for vision.extract>"}

Vision's only job is to pick which `name` matches the current screenshot.
The runner does the rest. This keeps the model from inventing coordinates.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Maybank — already logged in. Launch -> accounts page is visible.
# ---------------------------------------------------------------------------
MAYBANK = {
    "states": [
        {
            "name": "ios_home",
            "desc": (
                "iOS home screen — a grid of app icons, dock at the bottom. "
                "NO Spotlight search overlay, NO bank app UI, NO modal. "
                "Just the iPhone home screen with app icons."
            ),
            "do": {"type": "launch", "app": "MAE"},
        },
        {
            "name": "mae_loading",
            "desc": (
                "MAE app splash/loading screen — yellow/black branding with "
                "the MAE wordmark or tiger logo fills the screen, "
                "NO bottom tab bar, NO account data yet."
            ),
            "do": {"type": "wait", "seconds": 2.0},
        },
        {
            "name": "mae_session_expired",
            "desc": (
                "MAE 'Session Expired' modal — light grey screen with the "
                "heading 'Session Expired', subtext 'Looks like you've "
                "been inactive for 5 minutes. To continue, please login "
                "again.', a yellow 'Log In Now' button, an X close icon at "
                "top-right, and a decorative woman+hourglass illustration "
                "at the bottom of the screen."
            ),
            # Tap the yellow 'Log In Now' button (centered, ~36% down).
            "do": {"type": "tap_norm", "x": 0.50, "y": 0.36},
        },
        {
            "name": "mae_pin_prompt",
            "desc": (
                "MAE app PIN screen — a light grey upper area with the "
                "text '6-digit MAE app PIN' and 'Enter your current MAE "
                "app PIN', six small empty dots showing the PIN-entry "
                "indicators, a 'Forgot PIN' link, and an X close icon at "
                "top-right. The bottom HALF of the screen is a yellow "
                "numeric keypad with digits 1-9 in 3x3, plus backspace / "
                "0 / check (submit) on the bottom row."
            ),
            "do": {
                "type": "tap_pin",
                "key": "MAYBANK_APP_PASSWORD",
                # Keypad layout: digit -> (x_norm, y_norm).
                "layout": {
                    "1": [0.25, 0.69], "2": [0.50, 0.69], "3": [0.75, 0.69],
                    "4": [0.25, 0.78], "5": [0.50, 0.78], "6": [0.75, 0.78],
                    "7": [0.25, 0.87], "8": [0.50, 0.87], "9": [0.75, 0.87],
                    "0": [0.50, 0.93],
                },
                # Submit (check) button — bottom-right of keypad.
                "submit": [0.75, 0.93],
                "inter": 0.15,
            },
        },
        {
            "name": "mae_home_tab",
            "desc": (
                "MAE app is open with a dark bottom tab bar showing five "
                "tabs: Home / Accounts / Scan / Expenses / Apply. The "
                "'Home' tab is highlighted (yellow underline). The main "
                "body is mostly blank, just showing the status bar at top. "
                "NO account balances are visible yet."
            ),
            # 'Accounts' is tab 2 of 5; centered around x=30%.
            "do": {"type": "tap_norm", "x": 0.30, "y": 0.93},
        },
        {
            "name": "mae_accounts",
            "desc": (
                "MAE Accounts page — visible account names (e.g. 'Savings "
                "Account-i', 'Maybank Visa Debit') with balance amounts in "
                "MYR (e.g. 'RM 3.22'). The 'Accounts' tab is highlighted in "
                "the bottom tab bar. This is the success state."
            ),
            "do": {
                "type": "done",
                "extract": (
                    "This is the MAE (Maybank) Accounts page showing balances. "
                    "Extract EVERY visible account and balance. Return JSON: "
                    '{"balances": [{"account": "<name>", "amount": "<numeric>", '
                    '"currency": "MYR"}]}'
                ),
            },
        },
    ],
    "max_steps": 12,
}


# ---------------------------------------------------------------------------
# Global states — prepended to every bank's state list. Handles screens that
# can appear regardless of which bank we're trying to read.
# ---------------------------------------------------------------------------
GLOBAL_STATES = [
    {
        "name": "ipm_locked",
        "desc": (
            "iPhone Mirroring's own LOCK screen (NOT the iPhone lock screen) "
            "— text 'iPhone Mirroring Is Locked', a large lock icon with a "
            "fingerprint icon overlay, blurred background, and an 'Enter "
            "password' field at the bottom."
        ),
        "do": [
            {"type": "type_password", "key": "MAC_LOGIN_PASSWORD"},
            {"type": "press", "key": "enter"},
        ],
    },
    {
        "name": "ipm_connecting",
        "desc": (
            "iPhone Mirroring 'Connecting' transition screen — a dark/blue "
            "gradient background with the text 'Connecting to' followed by "
            "an iPhone model name (e.g. 'iPhone 16 Pro'). No buttons, no "
            "interactive elements. Just a brief transition."
        ),
        "do": {"type": "wait", "seconds": 3.0},
    },
    {
        "name": "ios_edit_mode",
        "desc": (
            "iOS home screen in EDIT / wiggle mode — top of screen shows "
            "'Edit' (left) and 'Done' (right) buttons; app icons may appear "
            "jiggly or have small minus/X badges. We can't reliably launch "
            "apps in this mode — exit by tapping 'Done'."
        ),
        "do": {"type": "tap_norm", "x": 0.88, "y": 0.05},
    },
    {
        "name": "spotlight_open",
        "desc": (
            "iOS Spotlight search overlay is visible — a search bar at "
            "the top or bottom with text typed in it, and a list of "
            "search results below (apps, mail, web suggestions, files). "
            "The previous home screen icons are dimmed or hidden. "
            "This means a launch sequence got stuck — recover by "
            "closing Spotlight."
        ),
        "do": {"type": "press", "key": "esc"},
    },
    {
        "name": "ipm_iphone_in_use",
        "desc": (
            "iPhone Mirroring DISCONNECT screen — a dark/black background "
            "showing a small iPhone illustration, the text 'iPhone in Use', "
            "the message 'iPhone Mirroring ended due to iPhone use. Lock "
            "your iPhone to connect.', and a blue 'Connect' button. iPhone "
            "Mirroring paused because the iPhone is being used in person."
        ),
        "do": {
            "type": "abort",
            "reason": "iPhone Mirroring is paused (you're using the iPhone). Lock the iPhone, then re-run.",
        },
    },
]


# ---------------------------------------------------------------------------
# Interbank (Peru) — password login. The trap: don't tap the four quick-action
# tiles or the "Activar Face ID" link; both lead nowhere useful and Face ID
# can trigger the "Lo sentimos / límite máximo de intentos" lockout.
# ---------------------------------------------------------------------------
INTERBANK = {
    "states": [
        {
            "name": "ios_home",
            "desc": (
                "iOS home screen — grid of app icons, dock at bottom. NO "
                "Spotlight overlay, NO Interbank UI. Just the iPhone home."
            ),
            "do": {"type": "launch", "app": "Interbank"},
        },
        {
            "name": "interbank_loading",
            "desc": (
                "Interbank app splash/loading/transition — EITHER a large "
                "green Interbank logo on white background, OR a split-screen "
                "animation with a green Interbank branded panel sliding in "
                "from the left while the login screen is partially visible "
                "on the right. NO fully visible 'Hola' greeting, NO fully "
                "visible password field. The app is still loading or "
                "transitioning."
            ),
            "do": {"type": "wait", "seconds": 2.0},
        },
        {
            "name": "interbank_main_login",
            "desc": (
                "Interbank MAIN login screen: hamburger '≡' icon top-left, "
                "Interbank logo top-center, NO back arrow at top. Shows "
                "'Hola <name>' / '¿Qué haremos hoy?' centered text, a row "
                "of FOUR green square quick-action tiles (Bloquear tarjeta / "
                "Pagar con QR / Servicios y recargas / Plinear a celular), "
                "and a BOTTOM GREEN panel containing a white password field "
                "labeled 'Ingresa tu contraseña' (with eye icon on right) "
                "and a blue 'Ingresar' button. Below that an 'Activar Face "
                "ID' link."
            ),
            # tap password field -> type -> tap Ingresar
            "do": [
                {"type": "tap_norm", "x": 0.50, "y": 0.573},
                {"type": "type_password", "key": "INTERBANK_APP_PASSWORD"},
                {"type": "tap_norm", "x": 0.50, "y": 0.649},
            ],
        },
        {
            "name": "interbank_subpage",
            "desc": (
                "An Interbank SUB-PAGE (NOT the main login). Distinguished "
                "by a back arrow '<' at top-left and a sub-flow header such "
                "as 'Plinear a celular', 'Pagar con QR', 'Servicios y "
                "recargas', or 'Bloquear tarjeta'. May also show a password "
                "panel at bottom — but we MUST NOT log in here; logging in "
                "on a sub-page does NOT show account balances."
            ),
            # tap the back arrow at top-left
            "do": {"type": "tap_norm", "x": 0.084, "y": 0.097},
        },
        {
            "name": "interbank_marketing_modal",
            "desc": (
                "Interbank marketing/promo modal overlay — a centered card "
                "with text like 'Ahorra para tus sueños' or similar Spanish "
                "promo copy, often with an illustration (piggy bank, etc.) "
                "and a green 'Entendido' button at the bottom of the card. "
                "Blocks interaction with whatever page is behind it."
            ),
            # Tap the green 'Entendido' button (centered, ~65% down).
            "do": {"type": "tap_norm", "x": 0.50, "y": 0.65},
        },
        {
            "name": "interbank_account_detail",
            "desc": (
                "Interbank 'Mi Cuenta' page (single account view, NOT the "
                "all-products list) — header reads 'Mi Cuenta' centered "
                "with a back arrow at top-left. Shows ONE account's name "
                "and balance, plus a blue '<<< >>>' carousel and a "
                "'Movimientos' transactions section at the bottom. We need "
                "to back out of this to reach the Productos list."
            ),
            # tap the green back arrow at top-left (coords verified by vision)
            "do": {"type": "tap_norm", "x": 0.086, "y": 0.136},
        },
        {
            "name": "interbank_productos",
            "desc": (
                "Interbank 'Productos' page — shows account balances in a "
                "vertical list. May show the '¿A quién le vas a Plinear "
                "hoy?' contacts row and 'T.C. referencial' exchange rate "
                "above the list, OR just the 'Productos' header if already "
                "scrolled. Each account row has a piggy-bank or card icon "
                "+ account name (e.g. 'Cuenta Simple Soles', 'dollars', "
                "'Millonaria Soles', 'Interbank Visa Infinite') + balance "
                "like 'S/ 10.25' or '$ 0.56'. Bottom has a tab bar with "
                "Inicio / Operaciones / QR / Beneficios / Para ti. "
                "THIS IS THE SUCCESS STATE."
            ),
            "do": {
                "type": "scroll_and_done",
                "down": 400,
                "extract": (
                    "This is the Interbank 'Productos' page listing ALL "
                    "accounts. Extract EVERY visible account row. Currency "
                    "is PEN if the symbol is S/, USD if it is $. Return JSON: "
                    '{"balances": [{"account": "<name>", "amount": '
                    '"<numeric, no symbol, keep two decimals>", '
                    '"currency": "PEN" or "USD", '
                    '"kind": "debit" if Saldo disponible else "credit"}]}'
                ),
            },
        },
        {
            "name": "interbank_session_expired",
            "desc": (
                "Interbank session-expired modal — a centered white card "
                "with a blue circle containing a warning/exclamation icon, "
                "the heading 'Lo sentimos' and the subtext 'Tu sesión ha "
                "expirado.' (literally 'your session has expired'), and a "
                "green 'Aceptar' button at the bottom. This is NOT a "
                "lockout — just dismiss it and re-login."
            ),
            # tap the green Aceptar button (centered, ~68% down)
            "do": {"type": "tap_norm", "x": 0.50, "y": 0.68},
        },
        {
            "name": "interbank_lockout",
            "desc": (
                "Interbank lockout modal — text contains 'límite máximo de "
                "intentos' (maximum login attempts reached). NOT to be "
                "confused with the session-expired modal which says 'Tu "
                "sesión ha expirado'. Lockout cannot be dismissed by "
                "tapping; user must unlock via Interbank's web portal."
            ),
            "do": {
                "type": "abort",
                "reason": "Interbank lockout — too many failed attempts; unlock via web portal",
            },
        },
    ],
    "max_steps": 14,
}


BANKS = {
    "maybank": MAYBANK,
    "interbank": INTERBANK,
}

# Prepend globals so every bank's classifier sees them too.
for _cfg in BANKS.values():
    _cfg["states"] = GLOBAL_STATES + _cfg["states"]
