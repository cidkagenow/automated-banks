"""Read OTP codes from email via IMAP (Yahoo and Gmail supported)."""

from __future__ import annotations

import email
import imaplib
import logging
import re
import time

log = logging.getLogger("web.otp")

PROVIDERS = {
    "yahoo.com": ("imap.mail.yahoo.com", 993),
    "gmail.com": ("imap.gmail.com", 993),
}


def _imap_host(email_addr: str) -> tuple[str, int]:
    """Pick IMAP server based on email domain."""
    domain = email_addr.rsplit("@", 1)[-1].lower()
    for key, (host, port) in PROVIDERS.items():
        if key in domain:
            return host, port
    raise ValueError(
        f"Unsupported email provider '{domain}'. "
        f"Supported: {', '.join(PROVIDERS)}. "
        "Add your provider to PROVIDERS in web/otp.py."
    )


def _strip_html(html: str) -> str:
    html = re.sub(r"<(style|script)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<[^>]+>", " ", html)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def _decode_payload(msg: email.message.Message) -> str:
    raw = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode("utf-8", errors="replace")
            if ct == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    raw = payload.decode("utf-8", errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        raw = payload.decode("utf-8", errors="replace") if payload else ""

    return _strip_html(raw) if raw else ""


def pre_clear_inbox(
    email_addr: str,
    app_password: str,
    sender_filter: str = "interbank",
) -> None:
    """Mark all unseen emails from sender as read. Call BEFORE triggering OTP."""
    host, port = _imap_host(email_addr)
    mail = imaplib.IMAP4_SSL(host, port)
    try:
        mail.login(email_addr, app_password)
        mail.select("INBOX")
        _, msg_ids = mail.search(None, f'(FROM "{sender_filter}" UNSEEN)')
        ids = msg_ids[0].split()
        for msg_id in ids:
            mail.store(msg_id, "+FLAGS", "\\Seen")
        log.info("pre-cleared %d stale email(s) as read", len(ids))
    finally:
        try:
            mail.logout()
        except Exception:
            pass


def fetch_otp(
    email_addr: str,
    app_password: str,
    sender_filter: str = "interbank",
    max_wait: int = 90,
    poll_interval: int = 5,
) -> str:
    """Poll IMAP for a fresh Interbank OTP email and return the 6-digit code.

    Auto-detects Yahoo or Gmail based on the email address.
    Assumes pre_clear_inbox was called before the OTP was triggered.
    """
    deadline = time.time() + max_wait
    log.info("waiting for fresh OTP email (max %ds, polling every %ds)", max_wait, poll_interval)

    while time.time() < deadline:
        try:
            code = _check_inbox(email_addr, app_password, sender_filter)
            if code:
                log.info("OTP found: %s", code)
                return code
        except Exception as e:
            log.warning("IMAP check failed: %s", e)

        remaining = deadline - time.time()
        if remaining > 0:
            time.sleep(min(poll_interval, remaining))

    raise TimeoutError(
        f"OTP email not received within {max_wait}s. "
        "Check your inbox manually."
    )


def _check_inbox(email_addr: str, app_password: str, sender_filter: str) -> str | None:
    host, port = _imap_host(email_addr)
    mail = imaplib.IMAP4_SSL(host, port)
    try:
        mail.login(email_addr, app_password)
        mail.select("INBOX")

        date_str = time.strftime("%d-%b-%Y")
        _, msg_ids = mail.search(
            None, f'(FROM "{sender_filter}" SINCE "{date_str}" UNSEEN)'
        )

        ids = msg_ids[0].split()
        if not ids:
            return None

        log.info("found %d unseen email(s) from '%s'", len(ids), sender_filter)

        for msg_id in reversed(ids):
            _, msg_data = mail.fetch(msg_id, "(RFC822)")
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            subject = str(msg.get("Subject", ""))
            sender = str(msg.get("From", ""))
            date = str(msg.get("Date", ""))
            log.info("checking email: subject=%r from=%r date=%r", subject, sender, date)
            body = _decode_payload(msg)

            contextual = re.search(
                r"(?:c[oó]digo|verificaci[oó]n|clave|code|otp)[^0-9]{0,30}(\d{6})\b",
                body,
                re.IGNORECASE,
            )
            if contextual:
                mail.store(msg_id, "+FLAGS", "\\Seen")
                return contextual.group(1)

            match = re.search(r"\b(\d{6})\b", body)
            if match:
                mail.store(msg_id, "+FLAGS", "\\Seen")
                return match.group(1)

        return None
    finally:
        try:
            mail.logout()
        except Exception:
            pass
