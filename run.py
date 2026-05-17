"""CLI entry point.

Usage:
  python run.py web interbank          # web scraper: Interbank balances + transactions
  python run.py web interbank --dry-run # fill form without submitting
  python run.py probe                  # show the iPhone Mirroring window bounds

For iPhone Mirroring agent (Maybank + Interbank), use the Claude Code
slash command instead:  /project:bank-balances
"""

from __future__ import annotations

import json
import logging
import sys

from dotenv import load_dotenv

load_dotenv()


def _web(bank: str, dry_run: bool = False) -> int:
    """Run a web-based bank scraper."""
    from agent import storage
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    bank = bank.lower()

    if bank == "interbank":
        from web.interbank import run_interbank
        result = run_interbank(dry_run=dry_run)
        if result["success"]:
            if result.get("balances"):
                storage.save(bank="interbank", kind="balance", result=result["balances"])
            if result.get("statements"):
                for stmt in result["statements"]:
                    if stmt.get("transactions"):
                        storage.save(bank="interbank", kind="statement", result={"statement": stmt})
        print(json.dumps(result, indent=2, default=str))
        return 0 if result["success"] else 1
    else:
        print(f"unknown web bank {bank!r}; currently supported: interbank")
        return 2


def _probe() -> int:
    from agent import window
    try:
        b = window.find()
    except window.WindowNotFoundError as e:
        print(e)
        return 1
    print(f"iPhone Mirroring: x={b.x} y={b.y} w={b.width} h={b.height} id={b.window_id}")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    if args[0] == "web" and len(args) >= 2:
        dry = "--dry-run" in args
        return _web(args[1], dry_run=dry)
    if args[0] == "probe":
        return _probe()
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
