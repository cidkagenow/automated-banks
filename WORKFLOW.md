# Workflow

End-to-end pipeline for a single bank run.

## Pipeline

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│  restart_ipm │────>│  close_front  │────>│  state machine │
│  (fresh IPM) │     │  app (swipe)  │     │  loop          │
└─────────────┘     └──────────────┘     └───────┬───────┘
                                                  │
                                    ┌─────────────┼─────────────┐
                                    ▼             ▼             ▼
                              ┌──────────┐ ┌──────────┐ ┌──────────┐
                              │screenshot│ │ classify  │ │ execute  │
                              │ capture  │ │ (Gemini)  │ │ action   │
                              └──────────┘ └──────────┘ └──────────┘
                                    │             │             │
                                    └─────────────┴──────┬──────┘
                                                         │
                                                  ┌──────▼──────┐
                                                  │   done?     │
                                                  │  extract    │
                                                  │  balances   │
                                                  └──────┬──────┘
                                                         │
                                                  ┌──────▼──────┐
                                                  │  save CSV + │
                                                  │  JSON snap  │
                                                  └─────────────┘
```

## Step-by-Step

### 1. Restart iPhone Mirroring
- Quit and reopen iPhone Mirroring to reset its input-handling state
- IPM throttles synthetic input after several runs; a restart clears this
- Wait for the window to appear (polls up to 10s)

### 2. Close Front App
- After IPM connects and the phone is unlocked, the runner opens the iOS app switcher (Cmd+2)
- Swipes up once to close the frontmost app
- This ensures the bank app launches fresh (resets scroll position, avoids stale sessions)
- Goes home (Cmd+1) afterward

### 3. State Machine Loop
Each iteration:

1. **Screenshot** — capture the iPhone Mirroring window via `screencapture -l <window_id>`
2. **Downscale** — resize to max 1568px for Gemini's input limit
3. **Classify** — send the screenshot + all state descriptions to Gemini; it returns which state matches
4. **Execute** — run the matched state's `do` action (tap, type, scroll, wait, etc.)
5. **Repeat** until a `done` or `scroll_and_done` state is reached, or `max_steps` is exceeded

### 4. Guard Rails
- **Unknown state**: presses Home and retries
- **Stuck detection**: same state 3 times in a row = abort with error
- **Max steps**: hard ceiling (12-14 per bank) prevents infinite loops
- **Abort states**: lockout screens trigger immediate abort with explanation

### 5. Extraction
When the final state is reached:
- `done`: extract balances from the current screenshot
- `scroll_and_done`: extract from current view, tap to establish scroll focus, scroll down, extract from scrolled view, merge both results (dedup by account+amount+currency)

### 6. Storage
- Append rows to `~/Desktop/bank_balances.csv`
- Save JSON snapshot to `data/snapshots.json`
- Save debug screenshots to `data/screenshots/`

## Multi-Bank Flow (`python run.py all`)

```
maybank ──(restart IPM)──> run state machine ──> save results
                                                      │
interbank ──(restart IPM)──> run state machine ──> save results
                                                      │
                                              write all to CSV
```

Each bank gets a fresh IPM restart. If one bank fails, the others still run.

## Input Methods

| Method | Used For | Why |
|--------|----------|-----|
| Quartz CGEvent click | In-app taps | Reliable with explicit click-count; pyautogui clicks get dropped |
| Quartz CGEvent drag | App switcher swipe-to-close | Works in system UI context |
| Phased scroll wheel events | Scrolling within apps | Only scroll method IPM forwards to iPhone |
| AppleScript keystrokes | Passwords, Spotlight search | Bypasses macOS Secure Input Mode |
| Cmd+1/2/3 shortcuts | Home, App Switcher, Spotlight | Keyboard shortcuts always work in IPM |
