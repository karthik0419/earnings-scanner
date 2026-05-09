"""
Detects the pullback entry zone after an earnings spike.
Looks for the consolidation low in D+1 to D+10 window.
"""

import pandas as pd
from datetime import timedelta


def detect_entry(df, result_date, spike_close):
    """
    Find the pullback entry after an earnings spike.

    Args:
        df: daily OHLCV DataFrame with DatetimeIndex
        result_date: date of result announcement
        spike_close: D0 closing price (the earnings day close)

    Returns dict with entry, stop, target, rr, pullback_days — or None if no valid entry.
    """
    if df is None or spike_close is None or spike_close <= 0:
        return None

    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.DatetimeIndex(df.index)

    df = df[~df.index.duplicated(keep="last")]
    result_ts = pd.Timestamp(result_date)

    # Get data from D+1 to D+15 after result
    start = result_ts + pd.Timedelta(days=1)
    end   = result_ts + pd.Timedelta(days=15)
    window = df[(df.index >= start) & (df.index <= end)]

    if len(window) < 2:
        return None

    # Pullback window: D+1 to D+10 (first 10 trading bars available)
    pullback_window = window.head(10)

    # Find the lowest close in pullback window
    min_close_idx = pullback_window["Close"].idxmin()
    pullback_low  = float(pullback_window.loc[min_close_idx, "Close"])
    pullback_days = len(df[(df.index > result_ts) & (df.index <= min_close_idx)])

    # Entry zone: at pullback low (we use pullback_low as the entry price)
    entry      = round(pullback_low, 2)
    stop_loss  = round(pullback_low * 0.97, 2)   # 3% below pullback low
    # Target: spike_close + 1.5x the pullback depth from spike
    move_size  = spike_close - pullback_low
    target     = round(spike_close + move_size * 1.5, 2)

    risk_amt   = entry - stop_loss
    reward_amt = target - entry

    if risk_amt <= 0:
        return None

    rr = round(reward_amt / risk_amt, 2)

    if rr < 1.5:
        return None

    return {
        "entry":         entry,
        "stop":          stop_loss,
        "target":        target,
        "rr":            rr,
        "pullback_days": pullback_days,
        "pullback_low":  pullback_low,
        "spike_close":   round(spike_close, 2),
    }
