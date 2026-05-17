"""Interbank Peru web portal automation."""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Page

from . import otp
from .browser import launch

log = logging.getLogger("web.interbank")

LOGIN_URL = "https://bancaporinternet.interbank.pe/login"
SHOTS_DIR = Path(__file__).resolve().parent.parent / "data" / "screenshots"


def _screenshot(page: Page, name: str) -> None:
    """Save a debug screenshot."""
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = SHOTS_DIR / f"web-interbank-{name}-{stamp}.png"
    page.screenshot(path=str(path))
    log.info("screenshot: %s", path)


def _env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"{key} not set in .env")
    return val


def _dismiss_modals(page: Page, nuke: bool = False) -> None:
    """Close any modal overlays (cookie consent, promos, etc.).

    With nuke=True, removes modal elements from the DOM entirely.
    Only use nuke=True on the dashboard (after login) — it breaks Vue state on login pages.
    """
    modal_buttons = [
        '.newLoginModalInfo button:has-text("Entendido")',
        '.ibk-modal button:has-text("Entendido")',
        '.ibk-modal button:has-text("Aceptar")',
        '.ibk-modal button',
        'button:has-text("Entendido")',
        'button:has-text("Aceptar")',
        'button:has-text("Cerrar")',
        'button:has-text("OK")',
        '[class*="close-modal"], [class*="modal-close"]',
        '.ibk-modal [class*="close"]',
    ]
    for _ in range(3):
        dismissed = False
        for selector in modal_buttons:
            btn = page.query_selector(selector)
            if btn and btn.is_visible():
                log.info("dismissing modal with: %s", selector)
                btn.click(force=True)
                page.wait_for_timeout(1500)
                dismissed = True
                break
        if not dismissed:
            break

    if nuke:
        removed = page.evaluate('''() => {
            const els = document.querySelectorAll('.ibk-modal, .modal-mask, .modal-position');
            els.forEach(el => el.remove());
            return els.length;
        }''')
        if removed:
            log.info("removed %d modal element(s) from DOM", removed)


def _click_virtual_keyboard(page: Page, password: str) -> None:
    """Type password via the on-screen virtual keyboard.

    Interbank renders each key as an SVG with id=<char> inside <a class="key">.
    The layout is scrambled each page load. For uppercase, click shift first.
    """
    pw_input = page.wait_for_selector('input[type="password"]', timeout=5000)
    pw_input.click()
    page.wait_for_timeout(1500)

    # Wait for keyboard keys to render
    page.wait_for_selector('.ibk-keyboard-virtual .key', timeout=10000)
    page.wait_for_timeout(500)
    _screenshot(page, "virtual-keyboard")

    shifted = False
    for i, char in enumerate(password):
        need_upper = char.isupper()

        if need_upper != shifted:
            # Shift key is a <div class="key keyremove special-key-cap-lock">
            shift_key = page.query_selector('.ibk-keyboard-virtual .special-key-cap-lock')
            if shift_key:
                shift_key.click()
                page.wait_for_timeout(200)
                log.info("shift toggled")
            else:
                log.warning("shift key not found — uppercase may fail")
            shifted = need_upper

        # Find key by SVG id — try both cases since shift may change ids
        key_el = None
        for lookup in [char.lower(), char.upper(), char]:
            key_el = page.query_selector(f'.ibk-keyboard-virtual svg[id="{lookup}"]')
            if key_el:
                break
        if not key_el:
            raise RuntimeError(
                f"Virtual keyboard key #{i+1} not found (char type: "
                f"{'letter' if char.isalpha() else 'digit' if char.isdigit() else 'special'})"
            )
        # Click the parent <a> link using Playwright (triggers proper events)
        parent = page.evaluate(
            '''(svg) => {
                const a = svg.closest('a');
                if (a) { a.setAttribute('data-pw-click', 'true'); return true; }
                return false;
            }''',
            key_el,
        )
        if parent:
            page.click('.ibk-keyboard-virtual a[data-pw-click="true"]')
            page.evaluate('''() => {
                const el = document.querySelector('a[data-pw-click="true"]');
                if (el) el.removeAttribute('data-pw-click');
            }''')
        else:
            key_el.click()
        page.wait_for_timeout(150)

    log.info("entered %d characters via virtual keyboard", len(password))

    # Click eye icon to reveal password for verification
    eye_icon = page.query_selector('img[src*="eye"], .ibk-textfield__icon-appended img, '
                                   '[class*="eye"], div.tw-cursor-pointer img')
    if eye_icon:
        eye_icon.click()
        page.wait_for_timeout(500)
        _screenshot(page, "password-revealed")
        log.info("password revealed — check screenshot")


def _fill_and_submit(page: Page, dry_run: bool = False) -> None:
    """Fill the login form and optionally submit.

    With dry_run=True, fills the form and reveals the password but does NOT
    click submit. Use this to verify the virtual keyboard works correctly
    without risking a failed login attempt.
    """
    # Dismiss any modal overlay blocking the form
    _dismiss_modals(page)

    dni = _env("INTERBANK_DNI")

    # Fill DNI — use keyboard to trigger Vue reactivity
    log.info("entering DNI")
    dni_input = page.wait_for_selector(
        'input[type="text"], input[type="number"], input[formcontrolname*="document"], '
        'input[placeholder*="documento"], input[name*="document"]',
        timeout=15000,
    )
    dni_input.click()
    page.wait_for_timeout(200)
    page.keyboard.press("Control+a")
    page.keyboard.type(dni, delay=20)
    page.wait_for_timeout(300)

    # Enter password via the on-screen virtual keyboard
    log.info("entering password via virtual keyboard")
    _click_virtual_keyboard(page, _env("INTERBANK_WEB_PASSWORD"))
    page.wait_for_timeout(500)

    _screenshot(page, "pre-submit")

    if dry_run:
        log.info("DRY RUN — form filled but NOT submitted. Check password-revealed screenshot.")
        page.wait_for_timeout(5000)
        return

    # Pre-clear stale OTP emails BEFORE triggering a new one
    log.info("clearing stale OTP emails before submit")
    otp_email = os.getenv("OTP_EMAIL") or _env("YAHOO_EMAIL")
    otp_pw = os.getenv("OTP_APP_PASSWORD") or _env("YAHOO_APP_PASSWORD")
    otp.pre_clear_inbox(otp_email, otp_pw)

    # Submit
    log.info("clicking submit")
    submit = page.query_selector(
        'button:has-text("Siguiente"), button:has-text("Ingresar")'
    )
    if submit:
        submit.click(force=True)
    else:
        page.click('button[type="submit"]', force=True)


def _login(page: Page, dry_run: bool = False) -> None:
    """Log into Interbank web portal: step 1 (DNI+password) then step 2 (clave digital/OTP)."""
    log.info("loading login page")
    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)
    _screenshot(page, "load")

    # Step 1: DNI + password
    _fill_and_submit(page, dry_run=dry_run)
    if dry_run:
        return
    page.wait_for_timeout(5000)
    _screenshot(page, "after-step1")

    # Read page text BEFORE dismissing modals — error messages live inside modals
    body_text = page.inner_text('body')
    body_lower = body_text.lower()

    if "lo sentimos" in body_lower or "inténtalo más tarde" in body_lower:
        raise RuntimeError(
            "Rate limited — 'Lo sentimos'. Too many login attempts. Wait a few minutes."
        )

    if "tiempo de conexión" in body_lower or "vuelve a ingresar" in body_lower:
        raise RuntimeError(
            "Session expired / rate limited — 'Tu tiempo de conexión finalizó'. Wait and try again."
        )

    if "límite máximo de intentos" in body_lower:
        raise RuntimeError("Account LOCKED — too many failed attempts. Unlock via Interbank web/call center.")

    if "datos incorrectos" in body_lower:
        raise RuntimeError(
            "Wrong credentials (Datos incorrectos). Check INTERBANK_DNI and "
            "INTERBANK_WEB_PASSWORD in .env. NOTE: your web password (clave web) "
            "may differ from your mobile app password."
        )

    # Dismiss modals now that we've checked for errors
    try:
        _dismiss_modals(page)
    except Exception:
        page.wait_for_timeout(3000)
    page.wait_for_timeout(1000)

    # Re-read after modal dismissal
    body_text = page.inner_text('body')

    # Check if we reached step 2: verification code or "Clave digital"
    step2_keywords = ["código de verificación", "clave digital", "codigo de verificacion"]
    found_step2 = any(kw in body_text.lower() for kw in step2_keywords)
    if found_step2:
        log.info("step 1 accepted — now on verification code screen")
    else:
        _screenshot(page, "step1-unexpected")
        log.info("page text after step 1: %s", body_text[:500])
        raise RuntimeError("Unexpected state after step 1 — check screenshot")

    # Step 2: Enter verification code (OTP sent to email)
    yahoo_email = os.getenv("OTP_EMAIL") or _env("YAHOO_EMAIL")
    yahoo_pw = os.getenv("OTP_APP_PASSWORD") or _env("YAHOO_APP_PASSWORD")
    log.info("fetching OTP from Yahoo Mail")
    code = otp.fetch_otp(yahoo_email, yahoo_pw)

    # Find the OTP input — try several strategies
    otp_input = page.query_selector(
        'input[type="password"], input[type="text"][name*="clave"], '
        'input[type="text"][name*="code"], input[type="text"][name*="otp"], '
        'input[type="tel"], input[type="number"], input[type="text"]'
    )
    if otp_input:
        readonly = page.evaluate('el => el.readOnly', otp_input)
        if readonly:
            log.info("entering code via virtual keyboard")
            _click_virtual_keyboard(page, code)
        else:
            log.info("entering code via text input")
            otp_input.click()
            page.wait_for_timeout(300)
            page.keyboard.type(code, delay=30)
    else:
        # Try individual digit inputs
        otp_inputs = page.query_selector_all('input[maxlength="1"]')
        if len(otp_inputs) >= len(code):
            for i, digit in enumerate(code):
                otp_inputs[i].fill(digit)
        else:
            raise RuntimeError("Could not find OTP input field")

    page.wait_for_timeout(500)
    _screenshot(page, "pre-otp-submit")

    # Submit step 2
    log.info("submitting verification code")
    submit = page.query_selector(
        'button:has-text("Ingresar"), button:has-text("Siguiente"), '
        'button:has-text("Continuar"), button:has-text("Validar")'
    )
    if submit:
        submit.click(force=True)
    else:
        page.click('button[type="submit"]', force=True)

    # Wait for result and check for errors
    log.info("waiting for dashboard")
    page.wait_for_timeout(8000)
    _screenshot(page, "dashboard")

    _dismiss_modals(page)
    page.wait_for_timeout(1000)

    body_text = page.inner_text('body')
    body_lower = body_text.lower()

    if "código ingresado es incorrecto" in body_lower or "codigo ingresado es incorrecto" in body_lower:
        _screenshot(page, "otp-rejected")
        raise RuntimeError(
            "OTP rejected — 'El código ingresado es incorrecto'. "
            "The code may have expired or been from an old email."
        )

    if "lo sentimos" in body_lower or "inténtalo más tarde" in body_lower:
        _screenshot(page, "rate-limited")
        raise RuntimeError(
            "Rate limited — 'Lo sentimos'. Too many login attempts. Wait a few minutes and try again."
        )

    if "superado el máximo" in body_lower:
        _screenshot(page, "max-attempts")
        raise RuntimeError("Max OTP attempts exceeded. Wait and try again.")

    # Check for dashboard indicators (we've passed the login)
    dashboard_indicators = ["consulta", "mis productos", "transferir", "saldo disponible"]
    on_dashboard = any(ind in body_lower for ind in dashboard_indicators)

    if not on_dashboard and "código de verificación" in body_lower:
        _screenshot(page, "still-on-otp")
        raise RuntimeError("Still on verification code screen after submit — OTP may have failed")

    log.info("login complete")


def _parse_amount(text: str) -> str:
    """Clean an amount string: remove currency symbols, keep sign and decimals."""
    text = text.strip()
    text = re.sub(r"^(?:S/|US\$|S/\.|US\$\.)\s*", "", text)
    text = text.replace(",", "")
    return text.strip()


def _extract_balances(page: Page) -> dict[str, Any]:
    """Extract all account balances from the post-login dashboard."""
    log.info("extracting balances")

    _dismiss_modals(page, nuke=True)
    page.wait_for_timeout(2000)
    _screenshot(page, "balances-page")

    balances: list[dict[str, str]] = []

    # Parse the visible text of the page — more robust than raw HTML
    body_text = page.inner_text("body")
    log.info("dashboard text (first 1000 chars): %s", body_text[:1000])

    # Pattern: account name line, then S/ or US$ amount on the next line
    # Dashboard shows: "Cuenta Simple Soles\nS/ 0.00\nSaldo disponible"
    amount_pattern = re.compile(
        r"((?:Cuenta|Visa|Tarjeta|Millonaria|American Express)[\w\s]*?(?:Soles|D[oó]lares|Infinite|Cl[aá]sica|Platinum|Access|Black)?)\s*\n\s*"
        r"((?:S/|US\$)\s*[\d,.]+)",
        re.IGNORECASE,
    )

    for match in amount_pattern.finditer(body_text):
        name = re.sub(r"\s+", " ", match.group(1).strip())
        raw_amount = match.group(2).strip()
        currency = "USD" if "US$" in raw_amount else "PEN"
        amount = _parse_amount(raw_amount)
        kind = "credit" if re.search(r"visa|tarjeta|american express", name, re.IGNORECASE) else "debit"
        if amount:
            balances.append({
                "account": name,
                "amount": amount,
                "currency": currency,
                "kind": kind,
            })

    # Keep all entries — same account name with different amounts are different accounts
    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for b in balances:
        key = (b["account"], b["currency"], b["amount"])
        if key not in seen:
            seen.add(key)
            unique.append(b)

    log.info("extracted %d balances", len(unique))
    return {"balances": unique}


def _click_account_card(page: Page, account_name: str) -> bool:
    """Click an account card on the dashboard by navigating via JS click."""
    # Use JS to find the text node and click the nearest ancestor link/card
    clicked = page.evaluate('''(name) => {
        // Find all text nodes containing the account name
        const walker = document.createTreeWalker(
            document.body, NodeFilter.SHOW_TEXT,
            { acceptNode: n => n.textContent.trim().includes(name)
                ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT }
        );
        let node = walker.nextNode();
        while (node) {
            let el = node.parentElement;
            // Walk up to find the clickable card container
            while (el && el !== document.body) {
                const tag = el.tagName.toLowerCase();
                if (tag === 'a' || el.getAttribute('role') === 'button'
                    || el.classList.toString().match(/card|product|item|cuenta/i)
                    || el.onclick || el.getAttribute('click')) {
                    el.click();
                    return el.innerText.substring(0, 100);
                }
                el = el.parentElement;
            }
            // Fallback: click the direct parent
            if (node.parentElement) {
                node.parentElement.click();
                return node.parentElement.innerText.substring(0, 100);
            }
            node = walker.nextNode();
        }
        return null;
    }''', account_name)

    if clicked:
        log.info("clicked account card via JS: %s → %s", account_name, clicked[:60])
        return True

    log.warning("account card not found: %s", account_name)
    return False


def _parse_statement_page(page: Page, account_name: str) -> dict[str, Any]:
    """Extract transactions from the current account detail/statement page."""
    _screenshot(page, f"statement-{account_name.replace(' ', '-').lower()}")

    body_text = page.inner_text("body")
    log.info("statement page text (first 1500 chars): %s", body_text[:1500])

    # Extract transactions via JS — read table cells directly
    transactions = page.evaluate('''() => {
        const rows = document.querySelectorAll('table tbody tr');
        const txns = [];
        for (const row of rows) {
            const cells = row.querySelectorAll('td');
            if (cells.length < 3) continue;
            const description = (cells[0]?.innerText || '').trim();
            const date = (cells[1]?.innerText || '').trim();
            const soles = (cells[2]?.innerText || '').trim();
            const dollars = cells.length > 3 ? (cells[3]?.innerText || '').trim() : '';
            if (!description && !date) continue;
            txns.push({ description, date, soles, dollars });
        }
        return txns;
    }''')

    parsed: list[dict[str, str]] = []
    for t in transactions:
        amount_str = t.get("dollars") or t.get("soles") or ""
        currency = "USD" if t.get("dollars") else "PEN"
        amount = _parse_amount(amount_str) if amount_str else ""
        # Strip leading minus for consistency, store sign separately
        negative = amount.startswith("-")
        if negative:
            amount = amount[1:]
        parsed.append({
            "date": t["date"],
            "description": t["description"],
            "amount": f"-{amount}" if negative else amount,
            "currency": currency,
        })

    log.info("extracted %d transactions for %s", len(parsed), account_name)
    return {
        "account": account_name,
        "transactions": parsed,
    }


def _go_back_to_dashboard(page: Page) -> None:
    """Navigate back to the main dashboard."""
    _dismiss_modals(page, nuke=True)
    page.evaluate('''() => {
        const links = document.querySelectorAll('a');
        for (const a of links) {
            if (a.textContent.trim() === 'Inicio') { a.click(); return; }
        }
        window.history.back();
    }''')
    log.info("navigating back to dashboard")
    page.wait_for_timeout(4000)
    _dismiss_modals(page, nuke=True)


def _extract_statements(page: Page) -> list[dict[str, Any]]:
    """Extract statements for each account listed in INTERBANK_WEB_ACCOUNTS."""
    accounts_str = os.getenv("INTERBANK_WEB_ACCOUNTS", "")
    if not accounts_str:
        log.info("INTERBANK_WEB_ACCOUNTS not set — skipping statement extraction")
        return []

    account_names = [a.strip() for a in accounts_str.split(",") if a.strip()]
    log.info("extracting statements for %d accounts: %s", len(account_names), account_names)

    statements: list[dict[str, Any]] = []

    for account_name in account_names:
        log.info("--- statement for: %s ---", account_name)
        _dismiss_modals(page, nuke=True)
        page.wait_for_timeout(1000)

        if not _click_account_card(page, account_name):
            statements.append({
                "account": account_name,
                "transactions": [],
                "error": "account card not found on dashboard",
            })
            continue

        page.wait_for_timeout(5000)
        _dismiss_modals(page, nuke=True)
        page.wait_for_timeout(1000)

        statement = _parse_statement_page(page, account_name)
        statements.append(statement)

        _go_back_to_dashboard(page)
        page.wait_for_timeout(2000)

    return statements


def run_interbank(headless: bool = False, dry_run: bool = False) -> dict[str, Any]:
    """Run the full Interbank web scraping flow.

    With dry_run=True, fills the login form but does NOT submit.
    Use this to verify virtual keyboard works before risking login attempts.

    Returns a dict with keys: success, balances, transactions, error.
    """
    try:
        with launch(headless=headless) as page:
            _login(page, dry_run=dry_run)
            if dry_run:
                return {
                    "success": True,
                    "balances": None,
                    "statements": None,
                    "error": "dry run — form filled but not submitted",
                }
            balances = _extract_balances(page)
            statements = _extract_statements(page)
            return {
                "success": True,
                "balances": balances,
                "statements": statements,
                "error": None,
            }
    except Exception as e:
        log.error("interbank web scraper failed: %s", e)
        return {
            "success": False,
            "balances": None,
            "statements": None,
            "error": str(e),
        }
