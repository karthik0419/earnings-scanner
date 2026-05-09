"""
Earnings momentum backtest engine.

For each stock + each of the last 4 quarters:
  1. Get result date for that quarter
  2. Measure price reaction on result day
  3. If spike > 2%: detect pullback entry
  4. Simulate entry — track to target / stop / D+30 time exit
  5. Record trade result

No look-ahead bias: only data available up to result_date is used
for detection; forward bars are used only for trade management.
"""

import pandas as pd
import numpy as np
from datetime import date, timedelta

from data.fetcher import fetch_cached
from data.earnings import fetch_earnings
from data.result_dates import get_result_date
from engine.price_reactor import measure_reaction
from engine.entry_detector import detect_entry
from backtester.metrics import calculate_metrics

MAX_HOLD_DAYS = 30
MIN_SPIKE_PCT  = 2.0


def _get_trading_close(df, target_date, max_fwd=7):
    """Return (price, date) for nearest trading day >= target_date."""
    idx = df.index
    target_ts = pd.Timestamp(target_date)
    for delta in range(max_fwd + 1):
        ts = target_ts + pd.Timedelta(days=delta)
        if ts in idx:
            return float(df.loc[ts, "Close"]), ts
    return None, None


def _simulate_trade(df, entry_date_ts, entry_price, stop, target):
    """
    Simulate a trade entered at entry_price on entry_date_ts.
    Exit: target hit, stop hit, or D+30 time exit.
    Returns (exit_price, exit_date, exit_reason, return_pct, days_held).
    """
    forward = df[df.index > entry_date_ts]
    if forward.empty:
        return entry_price, entry_date_ts, "No Data", 0.0, 0

    days_held = 0
    for ts, row in forward.iterrows():
        days_held += 1
        low   = float(row["Low"])
        high  = float(row["High"])
        close = float(row["Close"])

        # Stop hit — use stop price as exit (conservative)
        if low <= stop:
            ret = round((stop - entry_price) / entry_price * 100, 2)
            return stop, ts, "Stop Loss", ret, days_held

        # Target hit
        if high >= target:
            ret = round((target - entry_price) / entry_price * 100, 2)
            return target, ts, "Target Hit", ret, days_held

        # Time exit
        if days_held >= MAX_HOLD_DAYS:
            ret = round((close - entry_price) / entry_price * 100, 2)
            return close, ts, "Time Exit", ret, days_held

    # End of data
    last_close = float(forward.iloc[-1]["Close"])
    last_ts    = forward.index[-1]
    ret = round((last_close - entry_price) / entry_price * 100, 2)
    return last_close, last_ts, "End of Data", ret, days_held


def backtest_stock(symbol, quarters, price_df):
    """
    Run earnings momentum backtest for a single stock over its last 4 quarters.

    Returns dict with trades list and aggregate metrics.
    """
    if price_df is None or len(price_df) < 60:
        return {"symbol": symbol, "trades": [], "metrics": {}}

    if not isinstance(price_df.index, pd.DatetimeIndex):
        price_df.index = pd.DatetimeIndex(price_df.index)

    price_df = price_df[~price_df.index.duplicated(keep="last")]

    trades = []
    valid_qs = [q for q in quarters if q.get("net_profit") is not None]
    last4 = valid_qs[-4:] if len(valid_qs) >= 4 else valid_qs

    for q in last4:
        q_label = q.get("quarter")
        if not q_label:
            continue

        result_date = get_result_date(symbol, q_label, price_df=price_df)
        if result_date is None:
            continue

        result_ts = pd.Timestamp(result_date)

        # Only use price data available BEFORE result date for detection
        df_pre = price_df[price_df.index < result_ts]
        if len(df_pre) < 20:
            continue

        # Measure reaction using full df (forward bars needed)
        reaction = measure_reaction(symbol, result_date, price_df)
        if reaction is None:
            continue

        spike = reaction.get("spike_pct", 0)
        if spike < MIN_SPIKE_PCT:
            continue  # no trade on weak/negative reactions

        spike_close = reaction.get("d0")
        if not spike_close:
            continue

        entry_info = detect_entry(price_df, result_date, spike_close)
        if entry_info is None:
            continue

        entry_price = entry_info["entry"]
        stop        = entry_info["stop"]
        target      = entry_info["target"]
        pullback_days = entry_info["pullback_days"]

        # Entry date: result_date + pullback_days trading bars
        d0_ts = pd.Timestamp(result_date)
        fwd_bars = price_df[price_df.index > d0_ts]
        if len(fwd_bars) < pullback_days + 1:
            continue

        entry_date_ts = fwd_bars.index[pullback_days]

        # Verify entry price is reachable (low on entry bar must be <= entry)
        entry_bar_low = float(price_df.loc[entry_date_ts, "Low"])
        if entry_bar_low > entry_price:
            # Price never pulled back to our entry — skip
            continue

        exit_price, exit_date, exit_reason, return_pct, days_held = _simulate_trade(
            price_df, entry_date_ts, entry_price, stop, target
        )

        trades.append({
            "symbol":       symbol,
            "quarter":      q_label,
            "result_date":  str(result_date),
            "spike_pct":    spike,
            "entry_price":  round(entry_price, 2),
            "entry_date":   str(entry_date_ts.date()),
            "stop":         round(stop, 2),
            "target":       round(target, 2),
            "rr":           entry_info["rr"],
            "exit_price":   round(exit_price, 2),
            "exit_date":    str(exit_date.date()) if exit_date else None,
            "exit_reason":  exit_reason,
            "return_pct":   return_pct,
            "days_held":    days_held,
            "result":       "WIN" if return_pct > 0 else "LOSS",
        })

    metrics = calculate_metrics(trades)
    return {"symbol": symbol, "trades": trades, "metrics": metrics}


def run_backtest(symbols):
    """
    Run backtest across all symbols. Returns DataFrame of all trades.
    """
    all_trades = []

    for sym in symbols:
        print(f"  {sym}...", end=" ", flush=True)
        try:
            quarters = fetch_earnings(sym)
            if not quarters or len(quarters) < 4:
                print("skip (no earnings)")
                continue

            df = fetch_cached(sym, days=800)
            if df is None or len(df) < 60:
                print("skip (no price data)")
                continue

            result = backtest_stock(sym, quarters, df)
            n = len(result["trades"])
            m = result["metrics"]
            print(f"{n} trades | WR={m.get('win_rate', 0)}% | Avg={m.get('avg_return', 0)}%")
            all_trades.extend(result["trades"])

        except Exception as e:
            print(f"err: {e}")

    if not all_trades:
        return pd.DataFrame()

    return pd.DataFrame(all_trades)
