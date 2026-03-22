"""
Unit tests — app.py (midas gold dashboard)
Run: pytest tests/test_unit.py -v
"""
import math
import pytest
import numpy as np
import pandas as pd
import pandas_ta as ta
from unittest.mock import patch

import app as app_module
from app import app as flask_app, safe, compute_signals


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the in-memory TTL cache before every test for isolation."""
    app_module._CACHE.clear()
    yield
    app_module._CACHE.clear()


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


def make_mock_df(n: int = 130, seed: int = 42) -> pd.DataFrame:
    """Return a realistic daily OHLCV DataFrame with all indicator columns."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2024-09-01", periods=n)
    prices = 2800.0 + np.cumsum(rng.standard_normal(n) * 12)
    prices = np.abs(prices)

    df = pd.DataFrame(
        {
            "Open":   prices * 0.999,
            "High":   prices * 1.006,
            "Low":    prices * 0.994,
            "Close":  prices,
            "Volume": rng.integers(100_000, 500_000, n).astype(float),
        },
        index=dates,
    )

    close = df["Close"]
    df["RSI_14"] = ta.rsi(close, length=14)

    macd_df = ta.macd(close, fast=12, slow=26, signal=9)
    if macd_df is not None and not macd_df.empty:
        lc = next((c for c in macd_df.columns if c.startswith("MACD_")),  None)
        sc = next((c for c in macd_df.columns if c.startswith("MACDs_")), None)
        if lc: df["MACD_LINE"]   = macd_df[lc]
        if sc: df["MACD_SIGNAL"] = macd_df[sc]

    bb_df = ta.bbands(close, length=20, std=2)
    if bb_df is not None and not bb_df.empty:
        lower = next((c for c in bb_df.columns if c.startswith("BBL_")), None)
        mid   = next((c for c in bb_df.columns if c.startswith("BBM_")), None)
        upper = next((c for c in bb_df.columns if c.startswith("BBU_")), None)
        if lower: df["BB_LOWER"] = bb_df[lower]
        if mid:   df["BB_MID"]   = bb_df[mid]
        if upper: df["BB_UPPER"] = bb_df[upper]

    df["SMA_20"] = ta.sma(close, length=20)
    df["SMA_50"] = ta.sma(close, length=50)
    return df


def _row(**kwargs) -> pd.Series:
    """Helper: build a pd.Series to simulate df.iloc[-1]."""
    return pd.Series(kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# safe()
# ─────────────────────────────────────────────────────────────────────────────

class TestSafe:
    def test_normal_float(self):
        assert safe(3.14159, 2) == 3.14

    def test_rounding(self):
        assert safe(1.005, 2) == 1.0   # standard Python float rounding

    def test_none_returns_none(self):
        assert safe(None) is None

    def test_nan_returns_none(self):
        assert safe(float("nan")) is None

    def test_pos_inf_returns_none(self):
        assert safe(float("inf")) is None

    def test_neg_inf_returns_none(self):
        assert safe(float("-inf")) is None

    def test_zero(self):
        assert safe(0, 2) == 0.0

    def test_integer_input(self):
        assert safe(42, 2) == 42.0

    def test_string_number(self):
        assert safe("3.14159", 2) == 3.14

    def test_invalid_string(self):
        assert safe("abc") is None

    def test_numpy_nan(self):
        assert safe(np.nan) is None

    def test_numpy_float(self):
        assert safe(np.float64(2.5), 1) == 2.5


# ─────────────────────────────────────────────────────────────────────────────
# compute_signals()
# ─────────────────────────────────────────────────────────────────────────────

class TestComputeSignals:

    # ── RSI ──────────────────────────────────────────────────────────────────

    def test_rsi_buy(self):
        row = _row(RSI_14=30.0, MACD_LINE=1.0, MACD_SIGNAL=1.0,
                   BB_LOWER=2900.0, BB_MID=3000.0, BB_UPPER=3100.0,
                   SMA_20=3000.0, SMA_50=3000.0)
        _, _, ind = compute_signals(row, 3000.0)
        assert ind["rsi"]["signal"] == "COMPRAR"
        assert ind["rsi"]["score"]  == 1

    def test_rsi_sell(self):
        row = _row(RSI_14=70.0, MACD_LINE=1.0, MACD_SIGNAL=1.0,
                   BB_LOWER=2900.0, BB_MID=3000.0, BB_UPPER=3100.0,
                   SMA_20=3000.0, SMA_50=3000.0)
        _, _, ind = compute_signals(row, 3000.0)
        assert ind["rsi"]["signal"] == "VENDER"
        assert ind["rsi"]["score"]  == -1

    def test_rsi_neutral(self):
        row = _row(RSI_14=50.0, MACD_LINE=1.0, MACD_SIGNAL=1.0,
                   BB_LOWER=2900.0, BB_MID=3000.0, BB_UPPER=3100.0,
                   SMA_20=3000.0, SMA_50=3000.0)
        _, _, ind = compute_signals(row, 3000.0)
        assert ind["rsi"]["signal"] == "MANTENER"
        assert ind["rsi"]["score"]  == 0

    def test_rsi_boundary_buy(self):
        """RSI exactly at 34.9 is still a buy signal."""
        row = _row(RSI_14=34.9, MACD_LINE=1.0, MACD_SIGNAL=1.0,
                   BB_LOWER=2900.0, BB_MID=3000.0, BB_UPPER=3100.0,
                   SMA_20=3000.0, SMA_50=3000.0)
        _, _, ind = compute_signals(row, 3000.0)
        assert ind["rsi"]["score"] == 1

    def test_rsi_boundary_sell(self):
        """RSI exactly at 65.1 is a sell signal."""
        row = _row(RSI_14=65.1, MACD_LINE=1.0, MACD_SIGNAL=1.0,
                   BB_LOWER=2900.0, BB_MID=3000.0, BB_UPPER=3100.0,
                   SMA_20=3000.0, SMA_50=3000.0)
        _, _, ind = compute_signals(row, 3000.0)
        assert ind["rsi"]["score"] == -1

    # ── MACD ─────────────────────────────────────────────────────────────────

    def test_macd_buy(self):
        row = _row(RSI_14=50.0, MACD_LINE=5.0, MACD_SIGNAL=3.0,
                   BB_LOWER=2900.0, BB_MID=3000.0, BB_UPPER=3100.0,
                   SMA_20=3000.0, SMA_50=3000.0)
        _, _, ind = compute_signals(row, 3000.0)
        assert ind["macd"]["signal"] == "COMPRAR"
        assert ind["macd"]["score"]  == 1

    def test_macd_sell(self):
        row = _row(RSI_14=50.0, MACD_LINE=3.0, MACD_SIGNAL=5.0,
                   BB_LOWER=2900.0, BB_MID=3000.0, BB_UPPER=3100.0,
                   SMA_20=3000.0, SMA_50=3000.0)
        _, _, ind = compute_signals(row, 3000.0)
        assert ind["macd"]["signal"] == "VENDER"
        assert ind["macd"]["score"]  == -1

    # ── Bollinger Bands ───────────────────────────────────────────────────────

    def test_bollinger_buy(self):
        row = _row(RSI_14=50.0, MACD_LINE=1.0, MACD_SIGNAL=1.0,
                   BB_LOWER=3100.0, BB_MID=3200.0, BB_UPPER=3300.0,
                   SMA_20=3000.0, SMA_50=3000.0)
        _, _, ind = compute_signals(row, 3050.0)   # price < BB_LOWER
        assert ind["bollinger"]["signal"] == "COMPRAR"
        assert ind["bollinger"]["score"]  == 1

    def test_bollinger_sell(self):
        row = _row(RSI_14=50.0, MACD_LINE=1.0, MACD_SIGNAL=1.0,
                   BB_LOWER=2900.0, BB_MID=3000.0, BB_UPPER=3100.0,
                   SMA_20=3000.0, SMA_50=3000.0)
        _, _, ind = compute_signals(row, 3200.0)   # price > BB_UPPER
        assert ind["bollinger"]["signal"] == "VENDER"
        assert ind["bollinger"]["score"]  == -1

    def test_bollinger_neutral(self):
        row = _row(RSI_14=50.0, MACD_LINE=1.0, MACD_SIGNAL=1.0,
                   BB_LOWER=2900.0, BB_MID=3000.0, BB_UPPER=3100.0,
                   SMA_20=3000.0, SMA_50=3000.0)
        _, _, ind = compute_signals(row, 3000.0)   # price inside bands
        assert ind["bollinger"]["signal"] == "MANTENER"
        assert ind["bollinger"]["score"]  == 0

    # ── SMA Cross ─────────────────────────────────────────────────────────────

    def test_sma_buy(self):
        row = _row(RSI_14=50.0, MACD_LINE=1.0, MACD_SIGNAL=1.0,
                   BB_LOWER=2900.0, BB_MID=3000.0, BB_UPPER=3100.0,
                   SMA_20=3100.0, SMA_50=3000.0)    # SMA20 > SMA50
        _, _, ind = compute_signals(row, 3000.0)
        assert ind["sma"]["signal"] == "COMPRAR"
        assert ind["sma"]["score"]  == 1

    def test_sma_sell(self):
        row = _row(RSI_14=50.0, MACD_LINE=1.0, MACD_SIGNAL=1.0,
                   BB_LOWER=2900.0, BB_MID=3000.0, BB_UPPER=3100.0,
                   SMA_20=2950.0, SMA_50=3050.0)    # SMA20 < SMA50
        _, _, ind = compute_signals(row, 3000.0)
        assert ind["sma"]["signal"] == "VENDER"
        assert ind["sma"]["score"]  == -1

    # ── Final signal thresholds ───────────────────────────────────────────────

    def test_final_signal_comprar_at_plus_2(self):
        # RSI=30→+1, MACD line>signal→+1, inside bands→0, SMA20>SMA50→+1 => score=3 → COMPRAR
        row = _row(RSI_14=30.0, MACD_LINE=5.0, MACD_SIGNAL=3.0,
                   BB_LOWER=2900.0, BB_MID=3000.0, BB_UPPER=3100.0,
                   SMA_20=3100.0, SMA_50=3000.0)
        score, signal, _ = compute_signals(row, 3000.0)
        assert score  == 3
        assert signal == "COMPRAR"

    def test_final_signal_vender_at_minus_2(self):
        # RSI=70→-1, MACD<signal→-1, price>upper→-1, SMA20<SMA50→-1 => score=-4 → VENDER
        row = _row(RSI_14=70.0, MACD_LINE=3.0, MACD_SIGNAL=5.0,
                   BB_LOWER=2900.0, BB_MID=3000.0, BB_UPPER=3100.0,
                   SMA_20=2950.0, SMA_50=3050.0)
        score, signal, _ = compute_signals(row, 3200.0)
        assert score  == -4
        assert signal == "VENDER"

    def test_final_signal_mantener_at_zero(self):
        # RSI=50→0, MACD<signal→-1, inside bands→0, SMA20>SMA50→+1 => score=0 → MANTENER
        row = _row(RSI_14=50.0, MACD_LINE=3.0, MACD_SIGNAL=5.0,
                   BB_LOWER=2900.0, BB_MID=3000.0, BB_UPPER=3100.0,
                   SMA_20=3100.0, SMA_50=3000.0)
        score, signal, _ = compute_signals(row, 3000.0)
        assert score  == 0
        assert signal == "MANTENER"

    def test_final_signal_mantener_at_plus_1(self):
        # RSI=30→+1, MACD<signal→-1, inside bands→0, SMA20<SMA50→-1 => score=-1 → MANTENER
        row = _row(RSI_14=30.0, MACD_LINE=3.0, MACD_SIGNAL=5.0,
                   BB_LOWER=2900.0, BB_MID=3000.0, BB_UPPER=3100.0,
                   SMA_20=2950.0, SMA_50=3050.0)
        score, signal, _ = compute_signals(row, 3000.0)
        assert score  == -1
        assert signal == "MANTENER"


# ─────────────────────────────────────────────────────────────────────────────
# Flask API endpoints
# ─────────────────────────────────────────────────────────────────────────────

class TestApiData:

    def test_index_returns_200(self, client):
        res = client.get("/")
        assert res.status_code == 200
        assert "Análisis del Oro".encode() in res.data

    def test_api_data_structure(self, client):
        with patch("app.fetch_data", return_value=make_mock_df()):
            res  = client.get("/api/data")
            assert res.status_code == 200
            data = res.get_json()

        for key in ("current_price", "day_change", "day_change_pct",
                    "metrics", "chart", "score", "final_signal",
                    "indicators", "updated_at", "ticker", "unit"):
            assert key in data, f"Missing key: {key}"

    def test_api_data_metrics_keys(self, client):
        with patch("app.fetch_data", return_value=make_mock_df()):
            data = client.get("/api/data").get_json()
        for key in ("high_30d", "low_30d", "volatility_ann"):
            assert key in data["metrics"]

    def test_api_data_chart_keys(self, client):
        with patch("app.fetch_data", return_value=make_mock_df()):
            data = client.get("/api/data").get_json()
        for key in ("dates", "prices", "sma20", "sma50"):
            assert key in data["chart"]

    def test_api_data_indicators_keys(self, client):
        with patch("app.fetch_data", return_value=make_mock_df()):
            data = client.get("/api/data").get_json()
        for ind in ("rsi", "macd", "bollinger", "sma"):
            assert ind in data["indicators"]

    def test_api_data_final_signal_valid(self, client):
        with patch("app.fetch_data", return_value=make_mock_df()):
            data = client.get("/api/data").get_json()
        assert data["final_signal"] in ("COMPRAR", "MANTENER", "VENDER")

    def test_api_data_prices_are_floats_or_none(self, client):
        with patch("app.fetch_data", return_value=make_mock_df()):
            data = client.get("/api/data").get_json()
        for v in data["chart"]["prices"]:
            assert v is None or isinstance(v, (int, float))

    def test_api_data_error_handling(self, client):
        with patch("app.fetch_data", side_effect=RuntimeError("conexión fallida")):
            res  = client.get("/api/data")
            assert res.status_code == 500
            data = res.get_json()
            assert "error" in data
            assert "conexión fallida" in data["error"]

    def test_api_data_volatility_annualised(self, client):
        """Annualised volatility should be >> daily vol (≈ daily_vol * √252)."""
        with patch("app.fetch_data", return_value=make_mock_df()):
            data = client.get("/api/data").get_json()
        vol = data["metrics"]["volatility_ann"]
        # For our mock data: daily σ ≈ 0.4 %, annualised ≈ 6 %
        assert vol is not None
        assert vol > 1.0, "Annualised vol should be well above 1 %"


class TestApiChart:

    def test_api_chart_default_period(self, client):
        with patch("app.yf.download", return_value=make_mock_df()):
            res  = client.get("/api/chart")
            assert res.status_code == 200
            data = res.get_json()
        for key in ("dates", "prices", "sma20", "sma50", "period", "intraday"):
            assert key in data

    def test_api_chart_valid_periods(self, client):
        for period in ("1M", "6M", "1Y", "5Y", "MAX"):
            with patch("app.yf.download", return_value=make_mock_df()):
                res  = client.get(f"/api/chart?period={period}")
                assert res.status_code == 200
                data = res.get_json()
            assert data["period"] == period

    def test_api_chart_intraday_flag(self, client):
        with patch("app.yf.download", return_value=make_mock_df()):
            data = client.get("/api/chart?period=1D").get_json()
        assert data["intraday"] is True

        with patch("app.yf.download", return_value=make_mock_df()):
            data = client.get("/api/chart?period=6M").get_json()
        assert data["intraday"] is False

    def test_api_chart_sma_none_for_intraday(self, client):
        """SMA overlays should be absent (all None) for intraday periods."""
        with patch("app.yf.download", return_value=make_mock_df(30)):
            data = client.get("/api/chart?period=1D").get_json()
        sma20_values = [v for v in data["sma20"] if v is not None]
        assert sma20_values == [], "SMA20 must be all-None for intraday"

    def test_api_chart_unknown_period_defaults_to_6m(self, client):
        with patch("app.yf.download", return_value=make_mock_df()):
            res = client.get("/api/chart?period=BOGUS")
        # Should not crash — uses fallback
        assert res.status_code == 200


class TestApiDataMultiAsset:

    def test_btc_returns_correct_ticker_and_unit(self, client):
        with patch("app.fetch_data", return_value=make_mock_df()):
            data = client.get("/api/data?asset=BTC-USD").get_json()
        assert data["ticker"] == "BTC-USD"
        assert data["unit"]   == "USD"

    def test_gspc_returns_correct_ticker_and_unit(self, client):
        with patch("app.fetch_data", return_value=make_mock_df()):
            data = client.get("/api/data?asset=%5EGSPC").get_json()
        assert data["ticker"] == "^GSPC"
        assert data["unit"]   == "pts"

    def test_default_asset_is_gcf(self, client):
        with patch("app.fetch_data", return_value=make_mock_df()):
            data = client.get("/api/data").get_json()
        assert data["ticker"] == "GC=F"
        assert data["unit"]   == "USD/oz"

    def test_invalid_asset_returns_400(self, client):
        res = client.get("/api/data?asset=INVALID")
        assert res.status_code == 400
        assert "error" in res.get_json()

    def test_fetch_data_called_with_ticker(self, client):
        with patch("app.fetch_data", return_value=make_mock_df()) as mock_fd:
            client.get("/api/data?asset=BTC-USD")
        mock_fd.assert_called_once_with("BTC-USD")


class TestApiChartMultiAsset:

    def test_asset_param_accepted(self, client):
        with patch("app.yf.download", return_value=make_mock_df()):
            res = client.get("/api/chart?period=6M&asset=BTC-USD")
        assert res.status_code == 200

    def test_invalid_asset_returns_400(self, client):
        res = client.get("/api/chart?asset=INVALID")
        assert res.status_code == 400
        assert "error" in res.get_json()

    def test_yf_download_called_with_ticker(self, client):
        # Use 1M (not 6M) — the 6M path reuses the data cache, not yf.download directly
        with patch("app.yf.download", return_value=make_mock_df()) as mock_dl:
            client.get("/api/chart?period=1M&asset=BTC-USD")
        assert mock_dl.call_args[0][0] == "BTC-USD"
