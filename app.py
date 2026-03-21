from flask import Flask, render_template, jsonify
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import math

app = Flask(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def safe(val, decimals=2):
    """Return a rounded float, or None for NaN / Inf / None."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else round(f, decimals)
    except (TypeError, ValueError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Data fetching & indicator calculation
# ─────────────────────────────────────────────────────────────────────────────

def fetch_data() -> pd.DataFrame:
    """Download GC=F OHLCV data (~6 months) and attach all indicators."""
    df = yf.download("GC=F", period="6mo", progress=False, auto_adjust=True)
    if df.empty:
        raise RuntimeError("Yahoo Finance returned empty data for GC=F.")

    # Flatten MultiIndex columns produced by newer yfinance versions
    # e.g. ('Close', 'GC=F') → 'Close'
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.dropna(subset=["Close"], inplace=True)

    close = df["Close"]

    # RSI (14)
    df["RSI_14"] = ta.rsi(close, length=14)

    # MACD (12, 26, 9) — pick columns by prefix to survive version differences
    macd_df = ta.macd(close, fast=12, slow=26, signal=9)
    if macd_df is not None and not macd_df.empty:
        line_col   = next((c for c in macd_df.columns if c.startswith("MACD_")),  None)
        signal_col = next((c for c in macd_df.columns if c.startswith("MACDs_")), None)
        if line_col:   df["MACD_LINE"]   = macd_df[line_col]
        if signal_col: df["MACD_SIGNAL"] = macd_df[signal_col]

    # Bollinger Bands (20, 2σ)
    bb_df = ta.bbands(close, length=20, std=2)
    if bb_df is not None and not bb_df.empty:
        lower_col = next((c for c in bb_df.columns if c.startswith("BBL_")), None)
        mid_col   = next((c for c in bb_df.columns if c.startswith("BBM_")), None)
        upper_col = next((c for c in bb_df.columns if c.startswith("BBU_")), None)
        if lower_col: df["BB_LOWER"] = bb_df[lower_col]
        if mid_col:   df["BB_MID"]   = bb_df[mid_col]
        if upper_col: df["BB_UPPER"] = bb_df[upper_col]

    # Simple Moving Averages
    df["SMA_20"] = ta.sma(close, length=20)
    df["SMA_50"] = ta.sma(close, length=50)

    return df


# ─────────────────────────────────────────────────────────────────────────────
# Scoring logic
# ─────────────────────────────────────────────────────────────────────────────

def compute_signals(latest: pd.Series, close_price: float) -> tuple[int, str, dict]:
    """
    Score each indicator and derive the final signal.
    Returns (total_score, final_signal, indicators_dict).
    """
    score = 0
    indicators = {}

    # ── RSI ──────────────────────────────────────────────────────────────────
    rsi = safe(latest.get("RSI_14"), 2)
    if rsi is not None:
        if rsi < 35:
            rs, rt, rsig = +1, "Sobrevendido — posible rebote alcista", "COMPRAR"
        elif rsi > 65:
            rs, rt, rsig = -1, "Sobrecomprado — posible corrección bajista", "VENDER"
        else:
            rs, rt, rsig =  0, "Zona neutral (35–65)", "MANTENER"
    else:
        rs, rt, rsig = 0, "Datos insuficientes para calcular RSI", "MANTENER"
    score += rs
    indicators["rsi"] = {"value": rsi, "score": rs, "text": rt, "signal": rsig}

    # ── MACD ─────────────────────────────────────────────────────────────────
    macd_line   = safe(latest.get("MACD_LINE"),   4)
    macd_signal = safe(latest.get("MACD_SIGNAL"), 4)
    if macd_line is not None and macd_signal is not None:
        if macd_line > macd_signal:
            ms, mt, msig = +1, "Línea MACD sobre la señal — momentum alcista", "COMPRAR"
        else:
            ms, mt, msig = -1, "Línea MACD bajo la señal — momentum bajista", "VENDER"
    else:
        ms, mt, msig = 0, "Datos insuficientes para calcular MACD", "MANTENER"
    score += ms
    indicators["macd"] = {
        "line": macd_line, "signal_line": macd_signal,
        "score": ms, "text": mt, "signal": msig,
    }

    # ── Bollinger Bands ───────────────────────────────────────────────────────
    bb_lower = safe(latest.get("BB_LOWER"), 2)
    bb_mid   = safe(latest.get("BB_MID"),   2)
    bb_upper = safe(latest.get("BB_UPPER"), 2)
    if bb_lower is not None and bb_upper is not None:
        if close_price < bb_lower:
            bs, bt, bsig = +1, "Precio bajo la banda inferior — posible rebote", "COMPRAR"
        elif close_price > bb_upper:
            bs, bt, bsig = -1, "Precio sobre la banda superior — posible corrección", "VENDER"
        else:
            bs, bt, bsig =  0, "Precio dentro de las bandas — sin señal extrema", "MANTENER"
    else:
        bs, bt, bsig = 0, "Datos insuficientes para Bollinger", "MANTENER"
    score += bs
    indicators["bollinger"] = {
        "lower": bb_lower, "mid": bb_mid, "upper": bb_upper,
        "score": bs, "text": bt, "signal": bsig,
    }

    # ── SMA Cross ─────────────────────────────────────────────────────────────
    sma20 = safe(latest.get("SMA_20"), 2)
    sma50 = safe(latest.get("SMA_50"), 2)
    if sma20 is not None and sma50 is not None:
        if sma20 > sma50:
            ss, st, ssig = +1, "SMA20 sobre SMA50 — tendencia alcista de medio plazo", "COMPRAR"
        else:
            ss, st, ssig = -1, "SMA20 bajo SMA50 — tendencia bajista de medio plazo", "VENDER"
    else:
        ss, st, ssig = 0, "Datos insuficientes para cruce de medias", "MANTENER"
    score += ss
    indicators["sma"] = {
        "sma20": sma20, "sma50": sma50,
        "score": ss, "text": st, "signal": ssig,
    }

    # ── Final verdict ─────────────────────────────────────────────────────────
    if score >= 2:
        final = "COMPRAR"
    elif score <= -2:
        final = "VENDER"
    else:
        final = "MANTENER"

    return score, final, indicators


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/data")
def api_data():
    try:
        df = fetch_data()

        latest      = df.iloc[-1]
        prev_close  = float(df.iloc[-2]["Close"]) if len(df) >= 2 else float(latest["Close"])
        close_price = float(latest["Close"])
        day_change  = close_price - prev_close
        day_change_pct = (day_change / prev_close * 100) if prev_close else 0.0

        # Context metrics
        last_30       = df["Close"].iloc[-30:]
        returns_14    = df["Close"].pct_change().iloc[-14:]
        volatility_14 = float(returns_14.std()) * 100   # expressed as %

        # Chart data — last 90 sessions
        chart_df = df.tail(90)
        # strftime handles both timezone-aware and naive DatetimeIndex
        dates  = [str(d)[:10] for d in chart_df.index]
        prices = [safe(v, 2) for v in chart_df["Close"]]
        sma20  = [safe(v, 2) for v in chart_df.get("SMA_20", pd.Series(dtype=float))]
        sma50  = [safe(v, 2) for v in chart_df.get("SMA_50", pd.Series(dtype=float))]

        score, final_signal, indicators = compute_signals(latest, close_price)

        return jsonify({
            "current_price":   safe(close_price, 2),
            "day_change":      safe(day_change, 2),
            "day_change_pct":  safe(day_change_pct, 2),
            "metrics": {
                "high_30d":       safe(float(last_30.max()), 2),
                "low_30d":        safe(float(last_30.min()), 2),
                "volatility_14d": safe(volatility_14, 4),
            },
            "chart": {
                "dates":  dates,
                "prices": prices,
                "sma20":  sma20,
                "sma50":  sma50,
            },
            "score":        score,
            "final_signal": final_signal,
            "indicators":   indicators,
            "updated_at":   pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    app.run(debug=True)
