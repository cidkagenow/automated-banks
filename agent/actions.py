"""Synthetic input to iPhone Mirroring.

Mouse: pyautogui (sends to foreground app — that's why we focus IPM first).
Keyboard: AppleScript System Events. Required for password fields because
macOS Secure Input Mode blocks pyautogui's typing.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from dataclasses import dataclass

import pyautogui

from . import window

log = logging.getLogger("agent.actions")
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

ALLOWED_PASSWORD_KEYS = {
    "MAYBANK_APP_PASSWORD",
    "INTERBANK_APP_PASSWORD",
    "MAC_LOGIN_PASSWORD",
}


@dataclass
class Coord:
    """Map iPhone screenshot pixel (origin top-left) -> Mac screen point."""
    bounds: window.WindowBounds
    img_w: int
    img_h: int

    def to_screen(self, x: int, y: int) -> tuple[float, float]:
        sx = self.bounds.width / self.img_w
        sy = self.bounds.height / self.img_h
        return (self.bounds.x + x * sx, self.bounds.y + y * sy)

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x <= self.img_w and 0 <= y <= self.img_h


def _osa(script: str, timeout: float = 15.0) -> None:
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(
            f"osascript failed: {r.stderr.strip()}. "
            "Grant Accessibility + Automation permissions in System Settings."
        )


def _osa_keystroke(text: str) -> None:
    esc = text.replace("\\", "\\\\").replace('"', '\\"')
    _osa(f'tell application "System Events" to keystroke "{esc}"')


def _osa_cmd(letter: str) -> None:
    _osa(f'tell application "System Events" to keystroke "{letter}" using command down')


def _osa_keycode(code: int) -> None:
    _osa(f'tell application "System Events" to key code {code}')


KEY_CODES = {"enter": 36, "return": 36, "tab": 48, "esc": 53,
             "escape": 53, "backspace": 51, "space": 49}


def tap(c: Coord, x: int, y: int) -> None:
    if not c.in_bounds(x, y):
        raise ValueError(f"tap ({x},{y}) outside screenshot {c.img_w}x{c.img_h}")
    window.focus()
    sx, sy = c.to_screen(x, y)
    log.info("tap @ (%d,%d) screen(%.0f,%.0f)", x, y, sx, sy)
    _cg_click(sx, sy)


def _cg_click(sx: float, sy: float, hold: float = 0.15) -> None:
    """Tap via Quartz CGEvent with click-count=1 set. pyautogui's clicks were
    intermittently dropped by iPhone Mirroring; Quartz events with explicit
    click state are more reliable."""
    from Quartz import (  # type: ignore[import-not-found]
        CGEventCreateMouseEvent,
        CGEventPost,
        CGEventSetIntegerValueField,
        kCGEventLeftMouseDown,
        kCGEventLeftMouseUp,
        kCGEventMouseMoved,
        kCGHIDEventTap,
        kCGMouseButtonLeft,
        kCGMouseEventClickState,
    )

    # First move the cursor so any hover state updates.
    move = CGEventCreateMouseEvent(None, kCGEventMouseMoved, (sx, sy),
                                   kCGMouseButtonLeft)
    CGEventPost(kCGHIDEventTap, move)
    time.sleep(0.04)

    down = CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, (sx, sy),
                                   kCGMouseButtonLeft)
    CGEventSetIntegerValueField(down, kCGMouseEventClickState, 1)
    CGEventPost(kCGHIDEventTap, down)
    time.sleep(hold)
    up = CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, (sx, sy),
                                 kCGMouseButtonLeft)
    CGEventSetIntegerValueField(up, kCGMouseEventClickState, 1)
    CGEventPost(kCGHIDEventTap, up)


def swipe(c: Coord, x1: int, y1: int, x2: int, y2: int, duration: float = 0.18) -> None:
    """Synthetic swipe that iOS recognizes as a swipe (not a long-press).

    Uses Quartz CGEvent directly to drive continuous mouse-drag events at a
    fixed cadence with no initial dwell. pyautogui's dragTo() pauses briefly
    before motion starts; iOS via iPhone Mirroring interprets that pause as
    a long-press and enters icon-edit mode instead of advancing the page.
    """
    if not (c.in_bounds(x1, y1) and c.in_bounds(x2, y2)):
        raise ValueError("swipe endpoints outside screenshot bounds")
    window.focus()
    sx1, sy1 = c.to_screen(x1, y1)
    sx2, sy2 = c.to_screen(x2, y2)
    _cg_drag(sx1, sy1, sx2, sy2, duration=duration)


def _cg_drag(sx1: float, sy1: float, sx2: float, sy2: float,
             duration: float = 0.18) -> None:
    """Quartz-driven drag — issues continuous LeftMouseDragged events."""
    from Quartz import (  # type: ignore[import-not-found]
        CGEventCreateMouseEvent,
        CGEventPost,
        kCGEventLeftMouseDown,
        kCGEventLeftMouseDragged,
        kCGEventLeftMouseUp,
        kCGHIDEventTap,
        kCGMouseButtonLeft,
    )

    def post(kind, x, y):
        ev = CGEventCreateMouseEvent(None, kind, (x, y), kCGMouseButtonLeft)
        CGEventPost(kCGHIDEventTap, ev)

    post(kCGEventLeftMouseDown, sx1, sy1)
    steps = max(12, int(duration * 100))  # ~18 events per 0.18s
    for i in range(1, steps + 1):
        t = i / steps
        x = sx1 + (sx2 - sx1) * t
        y = sy1 + (sy2 - sy1) * t
        post(kCGEventLeftMouseDragged, x, y)
        time.sleep(duration / steps)
    post(kCGEventLeftMouseUp, sx2, sy2)


def type_text(text: str) -> None:
    window.focus()
    _osa_keystroke(text)


def type_password(env_key: str) -> None:
    if env_key not in ALLOWED_PASSWORD_KEYS:
        raise ValueError(f"password key {env_key!r} not allowed")
    pw = os.getenv(env_key)
    if not pw:
        raise RuntimeError(f"{env_key} not set in .env")
    window.focus()
    log.info("type_password key=%s len=%d", env_key, len(pw))
    _osa_keystroke(pw)


def press(key: str) -> None:
    code = KEY_CODES.get(key.lower())
    if code is None:
        raise ValueError(f"unsupported key {key!r}")
    window.focus()
    _osa_keycode(code)


def wait(seconds: float) -> None:
    time.sleep(max(0.0, min(seconds, 30.0)))


def scroll_down(c: Coord, amount: int = 200) -> None:
    """Trackpad-style scroll using phased scroll wheel events.

    CGEvent drags and plain scroll wheel events are ignored by iPhone
    Mirroring. Only phase-annotated scroll events (simulating a real
    two-finger trackpad gesture) are forwarded to the iPhone.
    """
    from Quartz import (
        CGEventCreateScrollWheelEvent,
        CGEventPost,
        CGEventSetIntegerValueField,
        CGEventSourceCreate,
        CGWarpMouseCursorPosition,
        kCGEventSourceStateHIDSystemState,
        kCGHIDEventTap,
        kCGScrollEventUnitPixel,
    )

    kCGScrollWheelEventScrollPhase = 99
    kCGScrollWheelEventMomentumPhase = 123

    window.focus()
    sx, sy = c.to_screen(c.img_w // 2, int(c.img_h * 0.5))
    CGWarpMouseCursorPosition((sx, sy))
    time.sleep(0.15)

    source = CGEventSourceCreate(kCGEventSourceStateHIDSystemState)
    per_tick = -8
    ticks = max(1, amount // abs(per_tick))

    ev = CGEventCreateScrollWheelEvent(source, kCGScrollEventUnitPixel, 1, per_tick)
    CGEventSetIntegerValueField(ev, kCGScrollWheelEventScrollPhase, 1)
    CGEventSetIntegerValueField(ev, kCGScrollWheelEventMomentumPhase, 0)
    CGEventPost(kCGHIDEventTap, ev)
    time.sleep(0.02)

    for _ in range(ticks):
        ev = CGEventCreateScrollWheelEvent(source, kCGScrollEventUnitPixel, 1, per_tick)
        CGEventSetIntegerValueField(ev, kCGScrollWheelEventScrollPhase, 2)
        CGEventSetIntegerValueField(ev, kCGScrollWheelEventMomentumPhase, 0)
        CGEventPost(kCGHIDEventTap, ev)
        time.sleep(0.015)

    ev = CGEventCreateScrollWheelEvent(source, kCGScrollEventUnitPixel, 1, 0)
    CGEventSetIntegerValueField(ev, kCGScrollWheelEventScrollPhase, 4)
    CGEventSetIntegerValueField(ev, kCGScrollWheelEventMomentumPhase, 0)
    CGEventPost(kCGHIDEventTap, ev)


def scroll_up(c: Coord, amount: int = 600) -> None:
    """Scroll up (positive direction). Same trackpad technique as scroll_down."""
    from Quartz import (
        CGEventCreateScrollWheelEvent,
        CGEventPost,
        CGEventSetIntegerValueField,
        CGEventSourceCreate,
        CGWarpMouseCursorPosition,
        kCGEventSourceStateHIDSystemState,
        kCGHIDEventTap,
        kCGScrollEventUnitPixel,
    )

    kCGScrollWheelEventScrollPhase = 99
    kCGScrollWheelEventMomentumPhase = 123

    window.focus()
    sx, sy = c.to_screen(c.img_w // 2, int(c.img_h * 0.5))
    CGWarpMouseCursorPosition((sx, sy))
    time.sleep(0.15)

    source = CGEventSourceCreate(kCGEventSourceStateHIDSystemState)
    per_tick = 8
    ticks = max(1, amount // per_tick)

    ev = CGEventCreateScrollWheelEvent(source, kCGScrollEventUnitPixel, 1, per_tick)
    CGEventSetIntegerValueField(ev, kCGScrollWheelEventScrollPhase, 1)
    CGEventSetIntegerValueField(ev, kCGScrollWheelEventMomentumPhase, 0)
    CGEventPost(kCGHIDEventTap, ev)
    time.sleep(0.02)

    for _ in range(ticks):
        ev = CGEventCreateScrollWheelEvent(source, kCGScrollEventUnitPixel, 1, per_tick)
        CGEventSetIntegerValueField(ev, kCGScrollWheelEventScrollPhase, 2)
        CGEventSetIntegerValueField(ev, kCGScrollWheelEventMomentumPhase, 0)
        CGEventPost(kCGHIDEventTap, ev)
        time.sleep(0.015)

    ev = CGEventCreateScrollWheelEvent(source, kCGScrollEventUnitPixel, 1, 0)
    CGEventSetIntegerValueField(ev, kCGScrollWheelEventScrollPhase, 4)
    CGEventSetIntegerValueField(ev, kCGScrollWheelEventMomentumPhase, 0)
    CGEventPost(kCGHIDEventTap, ev)


def go_home() -> None:
    """iPhone Mirroring's Cmd+1 — show iPhone home screen."""
    window.focus()
    _osa_cmd("1")


def open_app_switcher() -> None:
    """iPhone Mirroring's Cmd+2 — open the iPhone app switcher."""
    window.focus()
    _osa_cmd("2")


def close_front_app(bounds: window.WindowBounds) -> None:
    """Open the app switcher and swipe up once to close the frontmost app."""
    log.info("close_front_app: clearing frontmost app")
    window.focus()
    go_home()
    time.sleep(1.0)
    open_app_switcher()
    time.sleep(2.5)
    cx = bounds.x + bounds.width * 0.50
    y_start = bounds.y + bounds.height * 0.55
    y_end = bounds.y + bounds.height * 0.05
    _cg_drag(cx, y_start, cx, y_end, duration=0.20)
    time.sleep(1.2)
    go_home()
    time.sleep(1.5)


def restart_ipm(wait_after: float = 5.0) -> None:
    """Quit iPhone Mirroring and reopen it.

    Use between runs to reset IPM's input-handling state — empirically, IPM
    starts dropping synthetic taps after several agent runs in the same
    session, and a clean restart fixes it. The caller is responsible for
    waiting for any post-restart lock screen to be handled (the state
    machine has an `ipm_locked` global state that auto-types
    MAC_LOGIN_PASSWORD).
    """
    log.info("restarting iPhone Mirroring")
    subprocess.run(
        ["osascript", "-e", 'tell application "iPhone Mirroring" to quit'],
        capture_output=True, timeout=10,
    )
    time.sleep(1.5)
    subprocess.run(["open", "-a", "iPhone Mirroring"],
                   capture_output=True, timeout=10)
    time.sleep(wait_after)
    # Wait for the window to appear (up to ~10s).
    for _ in range(20):
        try:
            window.find()
            break
        except window.WindowNotFoundError:
            time.sleep(0.5)
    window.focus()
    time.sleep(0.5)


def launch(app_name: str) -> None:
    """Spotlight -> Cmd+a/Delete to focus+clear -> type -> Enter.

    Discovered today: iPhone Mirroring throttles `Cmd+<n>` shortcuts when
    they fire too soon after another modifier-key event. Both `Cmd+1` and
    `Esc` immediately before `Cmd+3` cause `Cmd+3` to be silently dropped.
    Workaround: skip Esc and Cmd+1 entirely. Open Spotlight directly with
    Cmd+3 — if Spotlight happened to already be open, Cmd+3 toggles it
    closed and the rest of the sequence fails harmlessly; the runner will
    classify ios_home next iteration and retry.

    The Cmd+a triggers iOS Spotlight's search field to take keyboard focus
    (the field doesn't auto-focus when Spotlight is opened via Cmd+3 alone).
    """
    window.focus()
    time.sleep(0.4)
    _osa_cmd("3")            # Spotlight (open or toggle)
    time.sleep(1.2)
    _osa_cmd("a")            # focus + select all cached
    time.sleep(0.3)
    _osa_keycode(51)         # delete to clear
    time.sleep(0.4)
    _osa_keystroke(app_name)
    time.sleep(1.0)
    _osa_keycode(36)         # Return — launch top hit
