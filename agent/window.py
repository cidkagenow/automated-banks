"""Locate the iPhone Mirroring window and bring it forward.

iPhone Mirroring on macOS Sequoia/Tahoe is a borderless floating window that
AppleScript can't enumerate. CoreGraphics (`CGWindowListCopyWindowInfo`) sees
it. To make synthetic clicks land we must raise it above ALL other windows
(NSWorkspace.activateWithOptions), not just within its own process — otherwise
overlapping windows from System Settings/Chrome can absorb the click.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass

from Quartz import (
    CGWindowListCopyWindowInfo,
    kCGNullWindowID,
    kCGWindowListOptionAll,
    kCGWindowListOptionOnScreenOnly,
)

APP_NAME = "iPhone Mirroring"


@dataclass(frozen=True)
class WindowBounds:
    x: int
    y: int
    width: int
    height: int
    window_id: int = 0


class WindowNotFoundError(RuntimeError):
    pass


def is_running() -> bool:
    res = subprocess.run(
        ["pgrep", "-x", APP_NAME], capture_output=True, text=True, timeout=3
    )
    return res.returncode == 0


def _candidates(option) -> list[dict]:
    info = CGWindowListCopyWindowInfo(option, kCGNullWindowID) or []
    out: list[dict] = []
    for w in info:
        if w.get("kCGWindowOwnerName") != APP_NAME:
            continue
        if w.get("kCGWindowName") != APP_NAME:
            continue
        b = w.get("kCGWindowBounds") or {}
        try:
            x, y = int(b["X"]), int(b["Y"])
            ww, hh = int(b["Width"]), int(b["Height"])
        except (KeyError, TypeError, ValueError):
            continue
        if ww < 200 or hh < 400 or hh <= ww:
            continue  # menu strips, not the iPhone screen
        out.append({"x": x, "y": y, "w": ww, "h": hh,
                    "id": int(w.get("kCGWindowNumber") or 0)})
    return out


def find() -> WindowBounds:
    if not is_running():
        raise WindowNotFoundError(
            "iPhone Mirroring is not running. Open it from Launchpad."
        )
    cands = _candidates(kCGWindowListOptionOnScreenOnly) or _candidates(kCGWindowListOptionAll)
    if not cands:
        raise WindowNotFoundError(
            "iPhone Mirroring is running but its phone window is hidden. "
            "Click its Dock icon to bring it forward."
        )
    best = max(cands, key=lambda c: c["w"] * c["h"])
    return WindowBounds(x=best["x"], y=best["y"], width=best["w"], height=best["h"],
                        window_id=best["id"])


def frontmost() -> str:
    res = subprocess.run(
        ["osascript", "-e",
         'tell application "System Events" to get name of first application process whose frontmost is true'],
        capture_output=True, text=True, timeout=5,
    )
    return res.stdout.strip()


def focus() -> None:
    """Raise iPhone Mirroring above all windows. No-op if already foreground."""
    if frontmost() == APP_NAME:
        return
    try:
        from AppKit import NSWorkspace  # type: ignore[import-not-found]
        ws = NSWorkspace.sharedWorkspace()
        for app in ws.runningApplications():
            if app.localizedName() == APP_NAME:
                # NSApplicationActivateIgnoringOtherApps | NSApplicationActivateAllWindows
                app.activateWithOptions_(0x1 | 0x2)
                break
        else:
            subprocess.run(
                ["osascript", "-e", f'tell application "{APP_NAME}" to activate'],
                capture_output=True, timeout=5,
            )
    except ImportError:
        subprocess.run(
            ["osascript", "-e", f'tell application "{APP_NAME}" to activate'],
            capture_output=True, timeout=5,
        )
    time.sleep(0.45)
