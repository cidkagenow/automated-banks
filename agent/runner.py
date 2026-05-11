"""The loop: screenshot -> classify state -> execute action -> repeat."""

from __future__ import annotations

import logging
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from . import actions, screenshot, vision, window

log = logging.getLogger("agent.runner")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SHOTS_DIR = PROJECT_ROOT / "data" / "screenshots"


@dataclass
class RunResult:
    success: bool
    steps: int
    result: dict[str, Any] = field(default_factory=dict)
    history: list[str] = field(default_factory=list)
    error: str | None = None


def _merge_balances(top: dict[str, Any], bot: dict[str, Any]) -> dict[str, Any]:
    """Merge two extraction results, deduplicating by (account, amount, currency)."""
    seen: dict[tuple, dict] = {}
    for entry in top.get("balances", []):
        key = (entry.get("account", ""), str(entry.get("amount", "")),
               entry.get("currency", ""))
        seen[key] = entry
    for entry in bot.get("balances", []):
        key = (entry.get("account", ""), str(entry.get("amount", "")),
               entry.get("currency", ""))
        seen[key] = entry
    return {"balances": list(seen.values())}


def _execute_one(do: dict[str, Any], coord: actions.Coord, small: Path) -> tuple[bool, dict]:
    """Run a single action dict. Returns (is_done, result_if_done)."""
    t = do["type"]
    if t == "launch":
        actions.launch(do["app"])
        time.sleep(2.5)
    elif t == "wait":
        actions.wait(float(do.get("seconds", 1.0)))
    elif t == "tap":
        actions.tap(coord, int(do["x"]), int(do["y"]))
    elif t == "tap_norm":
        x = int(coord.img_w * float(do["x"]))
        y = int(coord.img_h * float(do["y"]))
        actions.tap(coord, x, y)
    elif t == "swipe":
        x1 = int(coord.img_w * float(do["x1_norm"]))
        y1 = int(coord.img_h * float(do["y1_norm"]))
        x2 = int(coord.img_w * float(do["x2_norm"]))
        y2 = int(coord.img_h * float(do["y2_norm"]))
        actions.swipe(coord, x1, y1, x2, y2,
                      duration=float(do.get("duration", 0.4)))
    elif t == "find_and_tap_icon":
        _find_and_tap_icon(coord, small, str(do["app"]),
                           max_pages=int(do.get("max_pages", 5)))
        time.sleep(2.5)  # let the app open
    elif t == "type_password":
        actions.type_password(str(do["key"]))
    elif t == "tap_pin":
        _tap_pin(coord, do)
    elif t == "press":
        actions.press(str(do["key"]))
    elif t == "scroll_down":
        actions.scroll_down(coord, int(do.get("amount", 200)))
    elif t == "home":
        actions.go_home()
    elif t == "scroll_and_done":
        result_top = vision.extract(small, str(do["extract"]))
        # Tap page content to establish scroll focus before scrolling.
        actions.tap(coord, coord.img_w // 2, int(coord.img_h * 0.45))
        time.sleep(0.5)
        actions.scroll_down(coord, int(do.get("down", 200)))
        time.sleep(1.5)
        fresh = screenshot.capture(coord.bounds)
        fresh_small = screenshot.downscale(fresh)
        result_bot = vision.extract(fresh_small, str(do["extract"]))
        result = _merge_balances(result_top, result_bot)
        return True, result
    elif t == "done":
        result = vision.extract(small, str(do["extract"]))
        return True, result
    elif t == "abort":
        raise RuntimeError(str(do.get("reason", "abort requested")))
    else:
        raise RuntimeError(f"unknown do type {t!r}")
    return False, {}


def _tap_pin(coord: actions.Coord, do: dict[str, Any]) -> None:
    """Tap a PIN into an on-screen numeric keypad.

    `do` carries:
      - key:    env var holding the PIN (digits only)
      - layout: dict mapping each digit '0'..'9' to (x_norm, y_norm)
      - submit: optional (x_norm, y_norm) of the submit button; tapped after
                all digits if provided
      - inter:  optional sleep between key taps (default 0.15)
    """
    import os
    pin = os.getenv(str(do["key"]))
    if not pin:
        raise RuntimeError(f"{do['key']} not set in .env")
    layout = do["layout"]
    inter = float(do.get("inter", 0.15))
    log.info("tap_pin key=%s len=%d", do["key"], len(pin))
    for digit in pin:
        if digit not in layout:
            raise ValueError(f"PIN digit {digit!r} has no entry in layout")
        xn, yn = layout[digit]
        actions.tap(coord, int(coord.img_w * float(xn)),
                           int(coord.img_h * float(yn)))
        time.sleep(inter)
    submit = do.get("submit")
    if submit:
        actions.tap(coord, int(coord.img_w * float(submit[0])),
                           int(coord.img_h * float(submit[1])))


def _find_and_tap_icon(coord: actions.Coord, initial_small: Path,
                       app_name: str, max_pages: int) -> None:
    """Scan home pages for an app icon, tap when found.

    Uses vision to locate the icon on each visible home page. If not found,
    swipes right-to-left to advance to the next page. Tries up to
    `max_pages` pages. Raises if the icon isn't found anywhere.
    """
    small = initial_small
    bounds = coord.bounds
    for page in range(max_pages):
        log.info("looking for %r icon (page %d)", app_name, page + 1)
        loc = vision.find_icon(small, app_name)
        if loc is not None:
            x = int(coord.img_w * loc[0])
            y = int(coord.img_h * loc[1])
            log.info("found %r icon at norm (%.2f, %.2f)", app_name, *loc)
            actions.tap(coord, x, y)
            return
        # not on this page — swipe to the next one
        log.info("not on current page; swiping left")
        x1 = int(coord.img_w * 0.85); y1 = int(coord.img_h * 0.50)
        x2 = int(coord.img_w * 0.15); y2 = int(coord.img_h * 0.50)
        actions.swipe(coord, x1, y1, x2, y2, duration=0.4)
        time.sleep(1.0)
        # capture the new page for the next round
        raw = screenshot.capture(bounds)
        small = screenshot.downscale(raw)
    raise RuntimeError(
        f"icon for {app_name!r} not found after scanning {max_pages} pages"
    )


def _execute(do, coord: actions.Coord, small: Path) -> tuple[bool, dict]:
    """Run a state's `do` — either a single dict or a list of dicts run in
    sequence. List form lets one classifier turn perform a tightly-coupled
    sequence (e.g. tap-field, type-password, press-Enter) without the
    classifier re-checking the screen between steps.
    """
    items = do if isinstance(do, list) else [do]
    for item in items:
        done, result = _execute_one(item, coord, small)
        if done:
            return True, result
        time.sleep(0.4)
    return False, {}


def run(bank: str, config: dict[str, Any], save_shots: bool = True) -> RunResult:
    """Drive the iPhone through the bank's state machine until DONE."""
    states = config["states"]
    max_steps = int(config.get("max_steps", 15))
    candidates = [(s["name"], s["desc"]) for s in states]
    states_by_name = {s["name"]: s for s in states}

    history: list[str] = []
    run_stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if save_shots:
        SHOTS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        window.find()
    except window.WindowNotFoundError as e:
        return RunResult(success=False, steps=0, error=str(e))

    last_state: str | None = None
    repeat_count = 0
    apps_closed = False

    for step in range(1, max_steps + 1):
        try:
            bounds = window.find()
        except window.WindowNotFoundError as e:
            return RunResult(success=False, steps=step - 1, history=history, error=str(e))

        raw = screenshot.capture(bounds)
        small = screenshot.downscale(raw)
        sz = screenshot.size(small)
        coord = actions.Coord(bounds, sz[0], sz[1])

        if save_shots:
            dest = SHOTS_DIR / f"{bank}-{run_stamp}-step{step:02d}.png"
            shutil.copyfile(small, dest)

        try:
            state = vision.classify(small, candidates)
        except vision.VisionError as e:
            return RunResult(success=False, steps=step - 1, history=history, error=str(e))

        log.info("step %d: state=%s", step, state)
        history.append(f"step {step}: {state}")

        if state == "unknown":
            actions.go_home()
            time.sleep(1.0)
            last_state = None
            repeat_count = 0
            continue

        # Once past IPM infrastructure, close lingering apps so the
        # bank app launches fresh (resets scroll position, etc.).
        _INFRA = {"ipm_locked", "ipm_connecting"}
        if not apps_closed and state not in _INFRA:
            actions_bounds = window.find()
            actions.close_front_app(actions_bounds)
            apps_closed = True
            last_state = None
            repeat_count = 0
            continue

        # Loop guard: same state 3 times in a row = stuck.
        if state == last_state:
            repeat_count += 1
            if repeat_count >= 3:
                return RunResult(
                    success=False, steps=step, history=history,
                    error=f"stuck in state {state!r} for 3 consecutive steps",
                )
        else:
            repeat_count = 0
            last_state = state

        do = states_by_name[state]["do"]
        try:
            done, result = _execute(do, coord, small)
        except Exception as e:  # noqa: BLE001
            return RunResult(success=False, steps=step, history=history,
                             error=f"{state} action failed: {e}")

        if done:
            return RunResult(success=True, steps=step, result=result, history=history)
        time.sleep(0.8)

    return RunResult(success=False, steps=max_steps, history=history,
                     error="hit max_steps without reaching done")
