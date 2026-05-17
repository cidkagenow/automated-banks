"""CLI entry point.

Usage:
  python run.py web interbank        # web scraper: Interbank balances + transactions
  python run.py agent maybank        # phone agent: read Maybank balance once
  python run.py agent interbank      # phone agent: read Interbank balances once
  python run.py statement maybank          # get Maybank statement
  python run.py statement shadowsaa       # get Interbank shadowsaa statement
  python run.py statement cid             # get Interbank cid statement
  python run.py all                  # run Maybank + Interbank, append rows to ~/Desktop/bank_balances.csv
  python run.py probe                # show the iPhone Mirroring window bounds
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


def _agent(bank: str) -> int:
    from agent import actions, runner, states, storage
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    bank = bank.lower()
    config = states.BANKS.get(bank)
    if not config:
        print(f"unknown bank {bank!r}; choose from {list(states.BANKS)}")
        return 2
    actions.restart_ipm()
    result = runner.run(bank, config)
    if result.success:
        storage.save(bank=bank, kind="balance", result=result.result)
    print(json.dumps({
        "success": result.success,
        "steps": result.steps,
        "result": result.result,
        "error": result.error,
        "history": result.history,
    }, indent=2))
    return 0 if result.success else 1


def _statement(account: str) -> int:
    from agent import actions, runner, states, storage
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    account = account.lower()
    if account == "maybank":
        bank_key = "maybank_statement"
        bank_name = "maybank"
    elif account in states.STATEMENT_ACCOUNTS:
        bank_key = f"interbank_statement_{account}"
        bank_name = "interbank"
    else:
        valid = ["maybank"] + list(states.STATEMENT_ACCOUNTS)
        print(f"unknown account {account!r}; choose from {valid}")
        return 2
    config = states.BANKS[bank_key]
    actions.restart_ipm()
    result = runner.run(bank_key, config)
    if result.success:
        storage.save(bank=bank_name, kind="statement", result=result.result)
    print(json.dumps({
        "success": result.success,
        "account": account,
        "steps": result.steps,
        "result": result.result,
        "error": result.error,
        "history": result.history,
    }, indent=2))
    return 0 if result.success else 1


def _all() -> int:
    """Run every bank in sequence and append the balances to a CSV on Desktop.

    Banks are run in the order maybank -> tng -> interbank. If one bank fails,
    the others still run; their successful results are still written to the CSV.
    The CSV has columns: timestamp, bank, account, amount, currency, kind.
    """
    import csv
    from datetime import datetime, timezone
    from pathlib import Path

    from agent import runner, states, storage

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    banks = ["maybank", "interbank"]
    results: dict[str, dict | None] = {}
    errors: dict[str, str | None] = {}

    for bank in banks:
        print(f"\n=== {bank} ===")
        config = states.BANKS.get(bank)
        if not config:
            print(f"  unknown bank {bank!r}, skipping")
            results[bank] = None
            errors[bank] = "unknown bank"
            continue
        # Fresh IPM state per bank — empirically IPM throttles synthetic
        # input after a few agent runs and a quit+reopen clears it.
        from agent import actions
        actions.restart_ipm()
        result = runner.run(bank, config)
        if result.success:
            storage.save(bank=bank, kind="balance", result=result.result)
            results[bank] = result.result
            errors[bank] = None
            n = len(result.result.get("balances", []))
            print(f"  ok ({result.steps} steps, {n} accounts)")
        else:
            results[bank] = None
            errors[bank] = result.error
            print(f"  failed: {result.error}")

    # Append everything we got to a CSV on the Desktop.
    csv_path = Path.home() / "Desktop" / "bank_balances.csv"
    new_file = not csv_path.exists()
    timestamp = datetime.now(timezone.utc).isoformat()

    rows_written = 0
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["timestamp", "bank", "account", "amount",
                             "currency", "kind"])
        for bank, data in results.items():
            if data is None:
                continue
            for entry in data.get("balances", []):
                writer.writerow([
                    timestamp,
                    bank,
                    entry.get("account", ""),
                    entry.get("amount", ""),
                    entry.get("currency", ""),
                    entry.get("kind", ""),
                ])
                rows_written += 1

    print(f"\nWrote {rows_written} row(s) to {csv_path}")
    any_failed = any(v is not None for v in errors.values())
    return 1 if any_failed else 0


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
    if args[0] == "agent" and len(args) >= 2:
        return _agent(args[1])
    if args[0] == "statement" and len(args) >= 2:
        return _statement(args[1])
    if args[0] == "all":
        return _all()
    if args[0] == "probe":
        return _probe()
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
