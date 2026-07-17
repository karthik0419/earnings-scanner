"""
NSE result announcement date fetcher.
Primary: NSE event-calendar API.
Fallback: estimate as quarter_end + 45 days.
"""

import os
import json
import re
import requests
from datetime import date, datetime, timedelta

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

CACHE_FILE = os.path.join(CACHE_DIR, "result_dates.json")

NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com",
}

QUARTER_ENDS = {
    "Mar": (3, 31),
    "Jun": (6, 30),
    "Sep": (9, 30),
    "Dec": (12, 31),
}


def _is_fresh(path, max_age_hours=6):
    if not os.path.exists(path):
        return False
    age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(path))
    return age < timedelta(hours=max_age_hours)


def _load_cache():
    if _is_fresh(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def _save_cache(data):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def _fetch_nse_events():
    """Fetch event calendar from NSE with session cookie handling."""
    session = requests.Session()
    session.headers.update(NSE_HEADERS)

    try:
        # Get cookies first
        session.get("https://www.nseindia.com", timeout=10)
    except Exception:
        return []

    try:
        resp = session.get(
            "https://www.nseindia.com/api/event-calendar",
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _build_result_map(events):
    """Build {symbol: [{quarter_label, result_date}]} from NSE events."""
    result_map = {}
    for ev in events:
        purpose = ev.get("purpose", "") or ""
        symbol = ev.get("symbol", "") or ""
        dt_str = ev.get("date", "") or ""

        if not symbol or not dt_str:
            continue
        if "financial results" not in purpose.lower() and "quarterly results" not in purpose.lower():
            continue

        try:
            dt = datetime.strptime(dt_str[:10], "%d-%b-%Y").date()
        except Exception:
            try:
                dt = datetime.strptime(dt_str[:10], "%Y-%m-%d").date()
            except Exception:
                continue

        # Try to extract quarter from purpose string e.g. "Q2 Results Sep 2024"
        q_label = None
        m = re.search(r"(Mar|Jun|Sep|Dec)\s+(\d{4})", purpose, re.IGNORECASE)
        if m:
            q_label = f"{m.group(1).capitalize()} {m.group(2)}"

        if symbol not in result_map:
            result_map[symbol] = []
        result_map[symbol].append({"quarter": q_label, "result_date": str(dt)})

    return result_map


def _quarter_end_date(quarter_label):
    """Return the quarter end date for a label like 'Sep 2024'."""
    m = re.match(r"(Mar|Jun|Sep|Dec)\s+(\d{4})", quarter_label, re.IGNORECASE)
    if not m:
        return None
    month_name = m.group(1).capitalize()
    year = int(m.group(2))
    month, day = QUARTER_ENDS.get(month_name, (3, 31))
    return date(year, month, day)


def _estimate_result_date(quarter_label):
    """Fallback: quarter_end + 15 days (Indian companies announce quickly)."""
    qe = _quarter_end_date(quarter_label)
    if qe is None:
        return None
    return qe + timedelta(days=15)


def detect_result_date_from_price(quarter_label, price_df):
    """
    Auto-detect result date from price data by finding the largest
    single-day gap or volume spike within the expected announcement window.

    Indian results are typically announced:
      - Q1 (Jun): July 1–31
      - Q2 (Sep): October 1–31
      - Q3 (Dec): January 1–31
      - Q4 (Mar): April 1–May 15

    Returns date or None.
    """
    import pandas as pd
    import numpy as np

    qe = _quarter_end_date(quarter_label)
    if qe is None or price_df is None or len(price_df) < 10:
        return None

    if not isinstance(price_df.index, pd.DatetimeIndex):
        price_df.index = pd.DatetimeIndex(price_df.index)

    # Search window: quarter_end + 5 days to + 55 days
    start = pd.Timestamp(qe + timedelta(days=5))
    end   = pd.Timestamp(qe + timedelta(days=55))

    df = price_df[~price_df.index.duplicated(keep="last")].copy()
    window_idx = df[(df.index >= start) & (df.index <= end)].index

    if len(window_idx) < 3:
        return None

    # Compute gap % and volume ratio on full df, then slice to window
    prev_close = df["Close"].shift(1)
    gap_pct = ((df["Open"] - prev_close) / prev_close.abs() * 100).abs()
    avg_vol  = df["Volume"].rolling(20).mean()
    vol_ratio = (df["Volume"] / avg_vol).fillna(1)
    reaction_score = gap_pct * 0.7 + vol_ratio * 0.3

    window_scores = reaction_score.loc[window_idx]
    best_idx   = window_scores.idxmax()
    best_score = window_scores.loc[best_idx]

    # Only accept if the spike is meaningful
    if best_score < 2.0:
        return _estimate_result_date(quarter_label)

    return best_idx.date()


def get_result_date(symbol, quarter_label, price_df=None):
    """
    Return the result announcement date for a symbol + quarter.
    Priority:
      1. NSE event calendar (if available)
      2. Price-based auto-detection (largest spike in expected window)
      3. Estimated fallback (quarter_end + 15 days)
    """
    bare = symbol.replace(".NS", "").replace(".BO", "").upper()
    cache = _load_cache()

    if cache is None:
        events = _fetch_nse_events()
        cache = _build_result_map(events)
        _save_cache(cache)

    entries = cache.get(bare, [])
    for entry in entries:
        if entry.get("quarter") == quarter_label:
            try:
                return datetime.strptime(entry["result_date"], "%Y-%m-%d").date()
            except Exception:
                pass

    # Try proximity match even without label
    expected = _estimate_result_date(quarter_label)
    if expected:
        for entry in entries:
            try:
                dt = datetime.strptime(entry["result_date"], "%Y-%m-%d").date()
                if abs((dt - expected).days) <= 25:
                    return dt
            except Exception:
                continue

    # Price-based auto-detection
    if price_df is not None:
        detected = detect_result_date_from_price(quarter_label, price_df)
        if detected:
            return detected

    return expected


def fetch_upcoming_results(days_ahead=30):
    """Return list of stocks announcing results in next N days."""
    cache = _load_cache()
    if cache is None:
        events = _fetch_nse_events()
        cache = _build_result_map(events)
        _save_cache(cache)

    today = date.today()
    cutoff = today + timedelta(days=days_ahead)
    upcoming = []

    for symbol, entries in cache.items():
        for entry in entries:
            try:
                dt = datetime.strptime(entry["result_date"], "%Y-%m-%d").date()
                if today <= dt <= cutoff:
                    upcoming.append({
                        "symbol": symbol,
                        "quarter": entry.get("quarter"),
                        "result_date": dt,
                    })
            except Exception:
                continue

    upcoming.sort(key=lambda x: x["result_date"])
    return upcoming
