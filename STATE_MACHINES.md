# State Machines

Each bank is defined as a list of states. The vision model classifies the current screenshot against all state descriptions and picks the match. The runner then executes the matched state's action.

## Global States

These are prepended to every bank's state list. They handle screens that can appear regardless of which bank is being read.

```
┌─────────────────┐
│   ipm_locked     │──> type MAC_LOGIN_PASSWORD + press Enter
│   IPM lock screen│
└─────────────────┘

┌─────────────────┐
│  ipm_connecting  │──> wait 3s
│  "Connecting to" │
└─────────────────┘

┌─────────────────┐
│  ios_edit_mode   │──> tap "Done" button (top-right)
│  wiggle mode     │
└─────────────────┘

┌─────────────────┐
│  spotlight_open  │──> press Esc
│  search overlay  │
└─────────────────┘

┌─────────────────┐
│ ipm_iphone_in_use│──> ABORT: "Lock your iPhone to connect"
│  disconnect screen│
└─────────────────┘
```

## Maybank (MAE)

```
ios_home ──> launch "MAE" via Spotlight
    │
    ▼
mae_loading ──> wait 2s
    │
    ▼
mae_session_expired ──> tap "Log In Now" button
    │                       │
    ▼                       │
mae_pin_prompt ◄────────────┘
    │
    │  tap each PIN digit on the yellow numeric keypad
    │  using normalized keypad layout coordinates
    │  then tap submit (check) button
    │
    ▼
mae_home_tab ──> tap "Accounts" tab (2nd tab)
    │
    ▼
mae_accounts ──> DONE: extract all balances
    │
    ▼
  ┌──────────────────────────────┐
  │ {"balances": [               │
  │   {"account": "...",         │
  │    "amount": "...",          │
  │    "currency": "MYR"}       │
  │ ]}                           │
  └──────────────────────────────┘
```

**Notes:**
- PIN entry uses `tap_pin` action type with a keypad layout map (digit -> normalized x,y)
- Session expired modal can appear at any time; handled by tapping "Log In Now"
- Max steps: 12

## Interbank

```
ios_home ──> launch "Interbank" via Spotlight
    │
    ▼
interbank_loading ──> wait 2s
    │                 (covers splash screen AND
    │                  app launch slide animation)
    ▼
interbank_main_login ──> tap password field
    │                    type INTERBANK_APP_PASSWORD
    │                    tap "Ingresar" button
    ▼
    ├──> interbank_subpage ──> tap back arrow (top-left)
    │    (wrong page — back out)       │
    │                                  │
    ├──> interbank_marketing_modal ──> tap "Entendido"
    │    (promo popup)                 │
    │                                  │
    ├──> interbank_account_detail ──> tap back arrow
    │    (single account view)         │
    │                                  │
    ▼◄─────────────────────────────────┘
interbank_productos ──> SCROLL & DONE:
    │                   1. extract from current view (top accounts)
    │                   2. tap page for scroll focus
    │                   3. scroll down 400px
    │                   4. extract from scrolled view (bottom accounts)
    │                   5. merge & deduplicate
    ▼
  ┌──────────────────────────────────┐
  │ {"balances": [                   │
  │   {"account": "...",             │
  │    "amount": "...",              │
  │    "currency": "PEN" or "USD",  │
  │    "kind": "debit" or "credit"} │
  │ ]}                               │
  └──────────────────────────────────┘
```

**Error states:**
- `interbank_session_expired` — tap "Aceptar", then re-login
- `interbank_lockout` — ABORT: too many failed attempts, unlock via web portal

**Notes:**
- Login is password-based (NOT Face ID — activating Face ID can trigger lockout)
- The app sometimes opens to a sub-page or single account view; the agent navigates back
- Two-screenshot merge uses composite key (account, amount, currency) for dedup, preserving accounts with the same name but different balances
- Max steps: 14

## Action Types

| Type | Description |
|------|-------------|
| `launch` | Open app via Spotlight (Cmd+3, type name, Enter) |
| `wait` | Sleep for N seconds |
| `tap` | Tap at absolute pixel coordinates |
| `tap_norm` | Tap at normalized (0-1) coordinates |
| `tap_pin` | Tap a sequence of PIN digits on a numeric keypad |
| `type_password` | Type a password from .env via AppleScript |
| `press` | Press a key (enter, esc, etc.) |
| `scroll_down` | Trackpad-style phased scroll |
| `scroll_and_done` | Scroll + dual-screenshot extraction with merge |
| `swipe` | Drag gesture (used in app switcher) |
| `home` | Go to iOS home screen (Cmd+1) |
| `done` | Extract data from current screenshot |
| `abort` | Stop with error message |
