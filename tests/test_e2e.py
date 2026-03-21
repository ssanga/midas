"""
E2E tests — midas gold dashboard
Requires a running Flask server.

Run:
    python app.py &
    pytest tests/test_e2e.py -v --base-url=http://localhost:5000

Or via GitHub Actions (CI spins up Flask automatically).
"""
import pytest
from playwright.sync_api import Page, expect

# ── Helpers ───────────────────────────────────────────────────────────────────

TIMEOUT_DATA = 45_000   # ms — yfinance can be slow in CI


def wait_for_data(page: Page) -> None:
    """Block until the price card leaves the skeleton/loading state."""
    page.wait_for_selector("#current-price:not(.skeleton)", timeout=TIMEOUT_DATA)


# ─────────────────────────────────────────────────────────────────────────────
# Page load & basic structure
# ─────────────────────────────────────────────────────────────────────────────

def test_page_title(page: Page, base_url: str) -> None:
    page.goto(base_url)
    expect(page).to_have_title("Análisis del Oro — GC=F")


def test_header_visible(page: Page, base_url: str) -> None:
    page.goto(base_url)
    expect(page.locator("header")).to_be_visible()
    expect(page.locator("header h1")).to_contain_text("Análisis del Oro")


def test_gold_icon_in_header(page: Page, base_url: str) -> None:
    page.goto(base_url)
    # The SVG gold icon must be present inside h1
    expect(page.locator("header h1 svg")).to_be_visible()


def test_ticker_badge_visible(page: Page, base_url: str) -> None:
    page.goto(base_url)
    expect(page.locator("header .ticker")).to_contain_text("GC=F")


def test_period_buttons_present(page: Page, base_url: str) -> None:
    page.goto(base_url)
    for period in ("1D", "5D", "1M", "6M", "1Y", "5Y", "MAX"):
        btn = page.locator(f'.period-btn[data-period="{period}"]')
        expect(btn).to_be_visible()


def test_default_period_is_6m(page: Page, base_url: str) -> None:
    page.goto(base_url)
    active_btn = page.locator(".period-btn.active")
    expect(active_btn).to_have_attribute("data-period", "6M")


def test_help_button_present(page: Page, base_url: str) -> None:
    page.goto(base_url)
    expect(page.locator("#help-btn")).to_be_visible()


def test_refresh_button_present(page: Page, base_url: str) -> None:
    page.goto(base_url)
    expect(page.locator("#refresh-btn")).to_be_visible()


def test_chart_canvas_present(page: Page, base_url: str) -> None:
    page.goto(base_url)
    expect(page.locator("#priceChart")).to_be_visible()


def test_metric_cards_present(page: Page, base_url: str) -> None:
    page.goto(base_url)
    for el_id in ("#high-30d", "#low-30d", "#volatility"):
        expect(page.locator(el_id)).to_be_attached()


def test_indicator_cards_present(page: Page, base_url: str) -> None:
    page.goto(base_url)
    for card_id in ("#card-rsi", "#card-macd", "#card-bollinger", "#card-sma"):
        expect(page.locator(card_id)).to_be_visible()


# ─────────────────────────────────────────────────────────────────────────────
# Dark mode
# ─────────────────────────────────────────────────────────────────────────────

def test_dark_mode_toggle_to_dark(page: Page, base_url: str) -> None:
    page.goto(base_url)
    # Ensure we start in light mode
    page.evaluate("localStorage.setItem('theme', 'light')")
    page.reload()
    expect(page.locator("html")).to_have_attribute("data-theme", "light")

    page.click("#theme-btn")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")


def test_dark_mode_toggle_back_to_light(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.evaluate("localStorage.setItem('theme', 'dark')")
    page.reload()
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")

    page.click("#theme-btn")
    expect(page.locator("html")).to_have_attribute("data-theme", "light")


def test_dark_mode_persists_after_reload(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.evaluate("localStorage.setItem('theme', 'light')")
    page.reload()
    page.click("#theme-btn")   # switch to dark
    page.reload()
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")


def test_sun_icon_visible_in_dark_mode(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.evaluate("localStorage.setItem('theme', 'light')")
    page.reload()
    page.click("#theme-btn")
    # Moon should be hidden, sun visible
    expect(page.locator("#icon-moon")).to_be_hidden()
    expect(page.locator("#icon-sun")).to_be_visible()


# ─────────────────────────────────────────────────────────────────────────────
# Help modal
# ─────────────────────────────────────────────────────────────────────────────

def test_help_modal_opens_on_click(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.click("#help-btn")
    expect(page.locator("#help-modal")).to_have_class("open")


def test_help_modal_closes_on_x_button(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.click("#help-btn")
    page.click(".modal-close")
    expect(page.locator("#help-modal")).not_to_have_class("open")


def test_help_modal_closes_on_escape(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.click("#help-btn")
    page.keyboard.press("Escape")
    expect(page.locator("#help-modal")).not_to_have_class("open")


def test_help_modal_closes_on_overlay_click(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.click("#help-btn")
    # Click the overlay (the modal backdrop) — far corner
    page.click("#help-modal", position={"x": 10, "y": 10})
    expect(page.locator("#help-modal")).not_to_have_class("open")


def test_help_modal_contains_indicator_sections(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.click("#help-btn")
    modal = page.locator("#help-modal")
    for text in ("RSI", "MACD", "Bollinger", "SMA"):
        expect(modal).to_contain_text(text)


def test_help_modal_contains_scoring_table(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.click("#help-btn")
    expect(page.locator("#help-modal")).to_contain_text("scoring")


# ─────────────────────────────────────────────────────────────────────────────
# Period selector
# ─────────────────────────────────────────────────────────────────────────────

def test_period_button_becomes_active_on_click(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.click('.period-btn[data-period="1M"]')
    expect(page.locator('.period-btn[data-period="1M"]')).to_have_class("active")
    # Previous active (6M) should no longer be active
    expect(page.locator('.period-btn[data-period="6M"]')).not_to_have_class("active")


def test_chart_title_updates_on_period_change(page: Page, base_url: str) -> None:
    page.goto(base_url)
    # Wait a moment for initial chart title to settle
    page.wait_for_timeout(500)
    page.click('.period-btn[data-period="1Y"]')
    # Title should update (either loading or final label)
    page.wait_for_function(
        "document.getElementById('chart-title').textContent !== 'Cargando…'",
        timeout=TIMEOUT_DATA,
    )
    title = page.locator("#chart-title").inner_text()
    assert "1" in title or "año" in title.lower() or "Precio" in title


# ─────────────────────────────────────────────────────────────────────────────
# Data-dependent tests (need live yfinance — marked slow)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.slow
def test_price_loads_after_startup(page: Page, base_url: str) -> None:
    page.goto(base_url)
    wait_for_data(page)
    price_text = page.locator("#current-price").inner_text()
    assert "$" in price_text


@pytest.mark.slow
def test_signal_banner_shows_valid_signal(page: Page, base_url: str) -> None:
    page.goto(base_url)
    wait_for_data(page)
    banner = page.locator("#signal-banner").inner_text()
    assert any(s in banner for s in ("COMPRAR", "MANTENER", "VENDER"))


@pytest.mark.slow
def test_metrics_populated(page: Page, base_url: str) -> None:
    page.goto(base_url)
    wait_for_data(page)
    for el_id in ("#high-30d", "#low-30d", "#volatility"):
        text = page.locator(el_id).inner_text()
        assert text != "—", f"{el_id} still shows placeholder"


@pytest.mark.slow
def test_refresh_button_reloads_data(page: Page, base_url: str) -> None:
    page.goto(base_url)
    wait_for_data(page)
    page.click("#refresh-btn")
    # Button becomes disabled during load then re-enables
    page.wait_for_function(
        "!document.getElementById('refresh-btn').disabled",
        timeout=TIMEOUT_DATA,
    )
    expect(page.locator("#current-price")).not_to_have_class("skeleton")
