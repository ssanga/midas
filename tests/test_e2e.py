"""
E2E tests — midas gold dashboard
Requires a running Flask server.

Run:
    python app.py &
    pytest tests/test_e2e.py -v --base-url=http://localhost:5000

Or via GitHub Actions (CI spins up Flask automatically).
"""
import re
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
    expect(page.locator("#help-modal")).to_have_class(re.compile(r"\bopen\b"))


def test_help_modal_closes_on_x_button(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.click("#help-btn")
    page.click(".modal-close")
    expect(page.locator("#help-modal")).not_to_have_class(re.compile(r"\bopen\b"))


def test_help_modal_closes_on_escape(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.click("#help-btn")
    page.keyboard.press("Escape")
    expect(page.locator("#help-modal")).not_to_have_class(re.compile(r"\bopen\b"))


def test_help_modal_closes_on_overlay_click(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.click("#help-btn")
    # Click the overlay (the modal backdrop) — far corner
    page.click("#help-modal", position={"x": 10, "y": 10})
    expect(page.locator("#help-modal")).not_to_have_class(re.compile(r"\bopen\b"))


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
    # to_have_class matches the full class string — use regex to check for substring
    expect(page.locator('.period-btn[data-period="1M"]')).to_have_class(re.compile(r"\bactive\b"))
    # Previous active (6M) should no longer be active
    expect(page.locator('.period-btn[data-period="6M"]')).not_to_have_class(re.compile(r"\bactive\b"))


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


# ─────────────────────────────────────────────────────────────────────────────
# Asset selector
# ─────────────────────────────────────────────────────────────────────────────

def test_asset_buttons_present(page: Page, base_url: str) -> None:
    page.goto(base_url)
    for asset in ("GC=F", "BTC-USD", "^GSPC"):
        btn = page.locator(f'.asset-btn[data-asset="{asset}"]')
        expect(btn).to_be_visible()


def test_default_active_asset_is_gold(page: Page, base_url: str) -> None:
    page.goto(base_url)
    active_btn = page.locator(".asset-btn.active")
    expect(active_btn).to_have_attribute("data-asset", "GC=F")


def test_asset_switch_changes_active_button(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.click('.asset-btn[data-asset="BTC-USD"]')
    expect(page.locator('.asset-btn[data-asset="BTC-USD"]')).to_have_class(re.compile(r"\bactive\b"))
    expect(page.locator('.asset-btn[data-asset="GC=F"]')).not_to_have_class(re.compile(r"\bactive\b"))


def test_asset_switch_updates_header_title(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.click('.asset-btn[data-asset="BTC-USD"]')
    expect(page.locator("#header-title")).to_contain_text("Bitcoin")


def test_asset_switch_updates_ticker_badge(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.click('.asset-btn[data-asset="BTC-USD"]')
    expect(page.locator("#ticker-badge")).to_contain_text("BTC-USD")


def test_asset_switch_updates_url(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.click('.asset-btn[data-asset="BTC-USD"]')
    expect(page).to_have_url(re.compile(r"asset=BTC-USD"))


def test_gspc_asset_switch_updates_url(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.click('.asset-btn[data-asset="^GSPC"]')
    # ^GSPC encodes to %5EGSPC in URL
    expect(page).to_have_url(re.compile(r"asset=%5EGSPC", re.IGNORECASE))


def test_url_asset_param_sets_active_button(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}?asset=BTC-USD")
    expect(page.locator('.asset-btn[data-asset="BTC-USD"]')).to_have_class(re.compile(r"\bactive\b"))
    expect(page.locator('.asset-btn[data-asset="GC=F"]')).not_to_have_class(re.compile(r"\bactive\b"))


def test_no_page_reload_on_asset_switch(page: Page, base_url: str) -> None:
    page.goto(base_url)
    # Track navigations — a full reload would trigger a framenavigated event for the main URL
    navigations: list[str] = []
    page.on("framenavigated", lambda frame: navigations.append(frame.url) if frame == page.main_frame else None)
    page.click('.asset-btn[data-asset="BTC-USD"]')
    page.wait_for_timeout(500)
    # No full navigation should have occurred (pushState keeps the same frame)
    assert not any("BTC-USD" in url and url.startswith("http") for url in navigations), \
        "Asset switch should not trigger a full page navigation"


@pytest.mark.slow
def test_btc_price_loads_with_dollar_sign(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}?asset=BTC-USD")
    wait_for_data(page)
    price_text = page.locator("#current-price").inner_text()
    assert "$" in price_text


@pytest.mark.slow
def test_gspc_label_shows_pts_unit(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}?asset=%5EGSPC")
    wait_for_data(page)
    label_text = page.locator("#asset-label-unit").inner_text()
    assert "pts" in label_text.lower() or "500" in label_text
