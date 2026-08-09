"""Offline tests for the resilient window.Telegram.WebApp mock (KPI TMA env).

Coverage:
1. test_mock_injects_webln_telegram — after setup, the page's
   ``window.Telegram.WebApp`` is the mock with platform 'android'.
2. test_mock_has_open_invoice_stub — ``openInvoice`` is a function and
   records its argument in ``window.__TMA_MOCK__.openInvoiceCalls``.
3. test_mock_has_haptic_stub — ``HapticFeedback.impactOccurred`` exists and
   records the call.
4. test_mock_has_initdata_user — ``initDataUnsafe.user.id`` equals the id
   passed to setup_tma_env; ``initData`` is a non-empty signed-looking string.
5. test_real_app_gets_tma_env — the app's own JS sees ``window.Telegram`` /
   ``window.Telegram.WebApp`` (typeof checks + ready() callable).

All tests are OFFLINE: chromium is launched headless and only ever
navigates to ``about:blank`` (no network). Playwright itself is required
(installed in the project venv); tests skip cleanly if it is missing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright

# The module under test lives in scripts/kpi (no package __init__ there).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "kpi"))
import tma_env  # noqa: E402


@pytest.fixture(scope="module")
def browser():
    """One headless chromium for the whole module (offline, about:blank only)."""
    pw = sync_playwright().start()
    b = pw.chromium.launch(headless=True, args=["--no-sandbox"])
    yield b
    b.close()
    pw.stop()


def _fresh_page(browser):
    page = browser.new_page()
    page.goto("about:blank")
    return page


def test_mock_injects_webln_telegram(browser):
    page = _fresh_page(browser)
    tma_env.setup_tma_env(page, user_id=710000001)
    page.reload()
    wa = page.evaluate("window.Telegram && window.Telegram.WebApp")
    assert wa is not None, "window.Telegram.WebApp must exist after setup"
    assert wa["__tmaMock"] is True, "the installed object must be our mock"
    assert wa["platform"] == "android"
    assert wa["version"] == tma_env.DEFAULT_VERSION
    assert wa["colorScheme"] == "dark"
    assert page.evaluate("typeof window.Telegram.WebApp.ready") == "function"


def test_mock_has_open_invoice_stub(browser):
    page = _fresh_page(browser)
    tma_env.setup_tma_env(page)
    page.reload()
    is_fn = page.evaluate("typeof window.Telegram.WebApp.openInvoice")
    assert is_fn == "function", "openInvoice must be a function stub"
    page.evaluate("window.Telegram.WebApp.openInvoice('https://pay.example/inv/1')")
    calls = page.evaluate("window.__TMA_MOCK__.openInvoiceCalls")
    assert len(calls) == 1, "openInvoice must record its call"
    assert calls[0]["url"] == "https://pay.example/inv/1"


def test_mock_has_haptic_stub(browser):
    page = _fresh_page(browser)
    tma_env.setup_tma_env(page)
    page.reload()
    is_fn = page.evaluate(
        "typeof window.Telegram.WebApp.HapticFeedback.impactOccurred"
    )
    assert is_fn == "function", "HapticFeedback.impactOccurred must exist"
    page.evaluate(
        "window.Telegram.WebApp.HapticFeedback.impactOccurred('medium')"
    )
    calls = page.evaluate("window.__TMA_MOCK__.hapticCalls")
    assert len(calls) == 1, "impactOccurred must record the call"
    assert calls[0]["style"] == "medium"


def test_mock_has_initdata_user(browser):
    page = _fresh_page(browser)
    tma_env.setup_tma_env(page, user_id=424242, username="qa_probe")
    page.reload()
    uid = page.evaluate("window.Telegram.WebApp.initDataUnsafe.user.id")
    assert uid == 424242, "initDataUnsafe.user.id must match the passed id"
    uname = page.evaluate("window.Telegram.WebApp.initDataUnsafe.user.username")
    assert uname == "qa_probe"
    init_data = page.evaluate("window.Telegram.WebApp.initData")
    assert isinstance(init_data, str) and len(init_data) > 20
    assert "user=" in init_data and "hash=" in init_data


def test_real_app_gets_tma_env(browser):
    page = _fresh_page(browser)
    tma_env.setup_tma_env(page, user_id=710000042)
    page.reload()
    # The app's own JS (simulated by evaluating in the page) sees the env.
    assert page.evaluate("typeof window.Telegram") == "object"
    assert page.evaluate("typeof window.Telegram.WebApp") == "object"
    assert page.evaluate("typeof window.Telegram.WebApp.ready") == "function"
    assert page.evaluate("typeof window.Telegram.WebApp.openInvoice") == "function"
    # And the evidence log is reachable (used by the KPI report).
    ev = page.evaluate("window.__TMA_MOCK__")
    assert ev is not None and ev["platform"] == "android"
