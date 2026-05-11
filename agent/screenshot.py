"""Capture iPhone Mirroring's window contents."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from . import window


def capture(bounds: window.WindowBounds | None = None, out_path: Path | None = None) -> Path:
    """Screenshot the iPhone Mirroring window. Uses `screencapture -l <id>`
    which captures the window contents even when behind other windows."""
    if bounds is None:
        bounds = window.find()
    if out_path is None:
        fd, name = tempfile.mkstemp(prefix="iphone_", suffix=".png")
        import os; os.close(fd)
        Path(name).unlink(missing_ok=True)
        out_path = Path(name)

    cmds: list[list[str]] = []
    if bounds.window_id:
        cmds.append(["screencapture", "-x", "-o", "-l", str(bounds.window_id), str(out_path)])
    region_ok = bounds.x + bounds.width > 0 and bounds.y + bounds.height > 0
    if region_ok:
        cmds.append(["screencapture", "-x", "-R",
                     f"{bounds.x},{bounds.y},{bounds.width},{bounds.height}",
                     str(out_path)])

    last = ""
    for cmd in cmds:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and out_path.exists():
            return out_path
        last = r.stderr.strip() or last
        out_path.unlink(missing_ok=True)
    raise RuntimeError(f"screencapture failed: {last}. Grant Screen Recording permission.")


def downscale(path: Path, max_dim: int = 1568) -> Path:
    img = Image.open(path)
    w, h = img.size
    if max(w, h) <= max_dim:
        return path
    scale = max_dim / max(w, h)
    new_size = (int(w * scale), int(h * scale))
    out = path.with_suffix(".small.png")
    img.resize(new_size, Image.LANCZOS).save(out, "PNG", optimize=True)
    return out


def size(path: Path) -> tuple[int, int]:
    with Image.open(path) as im:
        return im.size
