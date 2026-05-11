"""JSON snapshot store for balance / transaction reads."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SNAPSHOTS = DATA / "snapshots.json"


def _ensure() -> None:
    DATA.mkdir(exist_ok=True)
    if not SNAPSHOTS.exists():
        SNAPSHOTS.write_text("[]", encoding="utf-8")


def save(bank: str, kind: str, result: dict[str, Any]) -> dict[str, Any]:
    """`kind` is 'balance' | 'transactions' | 'report'."""
    _ensure()
    entry = {
        "bank": bank,
        "kind": kind,
        "result": result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    items = load()
    items.append(entry)
    SNAPSHOTS.write_text(json.dumps(items, indent=2), encoding="utf-8")
    return entry


def load() -> list[dict[str, Any]]:
    _ensure()
    try:
        return json.loads(SNAPSHOTS.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def latest_per(bank: str, kind: str = "balance") -> dict[str, Any] | None:
    best = None
    for e in load():
        if e.get("bank") == bank and e.get("kind") == kind:
            if best is None or e["timestamp"] > best["timestamp"]:
                best = e
    return best
