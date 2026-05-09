"""
Measures stock price reaction around earnings result dates.
Calculates returns at D-1, D0, D+1, D+3, D+5, D+10, D+20.
"""

import pandas as pd
from datetime import date, timedelta


def _nearest_trading_date(df_index, target_date, direction="forward", max_days=5):
    """Find nearest available trading date in the index."""
    for delta in range(max_days + 1):
        if direction == "forward":
            candidate = target_date + timedelta(days=delta)
        else:
            candidate = target_date - timedelta(days=delta)
        candidate = pd.Timestamp(candidate)
        if candidate in df_index:
            return candidate
    return None


def _get_close(df, target_date, direction="forward", max_days=5):
    """Get close price for nearest trading date."""
    ts = _nearest_trading_date(df.index, target_date, direction=direction, max_days=max_days)
    if ts is None:
        return None, None
    return float(df.loc[ts, "Close"]), ts


def measure_reaction(symbol, result_date, df):
    """
    Measure price reaction around an earnings result date.

    Args:
        symbol: stock symbol (for logging)
        result_date: date of result announcement
        df: daily OHLCV DataFrame with DatetimeIndex

    Returns dict with price points and returns, or None if insufficient data.
    """
    if df is None or len(df) < 30:
        return None

    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.DatetimeIndex(df.index)

    # Drop duplicate index entries (keep last)
    df = df[~df.index.duplicated(keep="last")]

    result_ts = pd.Timestamp(result_date)

    # D-1: last close before result
    d_minus1_close, d_minus1_ts = _get_close(df, result_date - timedelta(days=1), direction="backward")
    if d_minus1_close is None:
        return None

    # D0: result day (or next trading day if after market hours)
    d0_close, d0_ts = _get_close(df, result_date, direction="forward")
    if d0_close is None:
        return None

    # Forward checkpoints
    def _fwd_close(n_days):
        target = d0_ts.date() + timedelta(days=n_days)
        c, _ = _get_close(df, target, direction="forward", max_days=7)
        return c

    d1  = _fwd_close(1)
    d3  = _fwd_close(3)
    d5  = _fwd_close(5)
    d10 = _fwd_close(10)
    d20 = _fwd_close(20)

    def _ret(price):
        if price is None or d_minus1_close == 0:
            return None
        return round((price - d_minus1_close) / d_minus1_close * 100, 2)

    spike = _ret(d0_close)
    if spike is None:
        return None

    # Classify reaction
    if spike > 5:
        classification = "strong"
    elif spike >= 2:
        classification = "moderate"
    elif spike >= 0:
        classification = "weak"
    else:
        classification = "negative"

    sustained = None
    if d20 is not None and d0_close != 0:
        sustained = round((d20 - d0_close) / d0_close * 100, 2)

    return {
        "symbol":         symbol,
        "result_date":    str(result_date),
        "d_minus1":       round(d_minus1_close, 2),
        "d0":             round(d0_close, 2),
        "d1":             round(d1, 2) if d1 else None,
        "d3":             round(d3, 2) if d3 else None,
        "d5":             round(d5, 2) if d5 else None,
        "d10":            round(d10, 2) if d10 else None,
        "d20":            round(d20, 2) if d20 else None,
        "spike_pct":      spike,
        "ret_d1":         _ret(d1),
        "ret_d3":         _ret(d3),
        "ret_d5":         _ret(d5),
        "ret_d10":        _ret(d10),
        "ret_d20":        _ret(d20),
        "sustained_pct":  sustained,
        "classification": classification,
    }


def avg_spike(reactions):
    """Average spike % across a list of reaction dicts. Excludes negatives."""
    spikes = [r["spike_pct"] for r in reactions if r and r.get("spike_pct", 0) > 0]
    return round(sum(spikes) / len(spikes), 2) if spikes else 0.0
