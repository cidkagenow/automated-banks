"""Playwright browser lifecycle management."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

log = logging.getLogger("web.browser")

@contextmanager
def launch(headless: bool = False) -> Generator[Page, None, None]:
    """Launch Chromium and yield a page. Cleans up on exit."""
    with sync_playwright() as pw:
        browser: Browser = pw.chromium.launch(
            headless=headless,
            slow_mo=300,
            channel="chrome",
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context: BrowserContext = browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="es-PE",
            timezone_id="America/Lima",
        )
        # Hide automation flags so sites don't block functionality
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            delete navigator.__proto__.webdriver;
        """)
        page: Page = context.new_page()
        log.info("browser launched (headless=%s)", headless)
        try:
            yield page
        finally:
            context.close()
            browser.close()
            log.info("browser closed")
