"""
Full NSE equity universe fetcher.
Downloads daily bhavcopy from NSE, filters by price + volume,
returns ~800-1000 liquid, actionable stocks.
Fallback: nifty500.txt if bhavcopy unavailable.
"""

import os
import requests
import pandas as pd
from datetime import date, timedelta, datetime

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache")
BASE_DIR  = os.path.join(os.path.dirname(__file__), "..")
os.makedirs(CACHE_DIR, exist_ok=True)

NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Referer": "https://www.nseindia.com",
}

MIN_PRICE  = 20       # filter out penny stocks
MIN_VOLUME = 50000    # minimum daily traded quantity


def _cache_path(dt):
    return os.path.join(CACHE_DIR, f"nse_universe_{dt}.csv")


def _is_fresh(path, max_age_hours=24):
    if not os.path.exists(path):
        return False
    age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(path))
    return age < timedelta(hours=max_age_hours)


def _fetch_bhavcopy(dt):
    """Try to download NSE bhavcopy for a given date."""
    session = requests.Session()
    session.headers.update(NSE_HEADERS)

    # Get cookies first
    try:
        session.get("https://www.nseindia.com", timeout=10)
    except Exception:
        pass

    date_str = dt.strftime("%d%m%Y")
    url = (
        f"https://nsearchives.nseindia.com/products/content/"
        f"sec_bhavdata_full_{date_str}.csv"
    )

    try:
        resp = session.get(url, timeout=20)
        if resp.status_code == 200 and len(resp.content) > 1000:
            return resp.text
    except Exception:
        pass

    return None


def _parse_bhavcopy(csv_text):
    """Parse bhavcopy CSV and return filtered DataFrame."""
    from io import StringIO
    try:
        df = pd.read_csv(StringIO(csv_text))
        df.columns = [c.strip() for c in df.columns]

        # Normalise column names — NSE changes them occasionally
        col_map = {}
        for c in df.columns:
            cu = c.upper().replace(" ", "_")
            if "SYMBOL" in cu:
                col_map[c] = "SYMBOL"
            elif "SERIES" in cu:
                col_map[c] = "SERIES"
            elif "CLOSE" in cu:
                col_map[c] = "CLOSE"
            elif "TTL_TRD_QNTY" in cu or "TOTTRDQTY" in cu or "TOTAL_TRADED" in cu or "TTL_TRD" in cu:
                col_map[c] = "VOLUME"
        df = df.rename(columns=col_map)

        required = {"SYMBOL", "SERIES", "CLOSE", "VOLUME"}
        if not required.issubset(set(df.columns)):
            return None

        df = df[df["SERIES"].str.strip() == "EQ"].copy()
        df["CLOSE"]  = pd.to_numeric(df["CLOSE"],  errors="coerce")
        df["VOLUME"] = pd.to_numeric(df["VOLUME"], errors="coerce")
        df = df.dropna(subset=["CLOSE", "VOLUME"])
        df = df[(df["CLOSE"] >= MIN_PRICE) & (df["VOLUME"] >= MIN_VOLUME)]
        df["SYMBOL"] = df["SYMBOL"].str.strip()
        return df[["SYMBOL", "CLOSE", "VOLUME"]].reset_index(drop=True)

    except Exception:
        return None


def _load_fallback():
    """Load nifty500.txt as fallback universe."""
    path = os.path.join(BASE_DIR, "nifty500.txt")
    try:
        with open(path) as f:
            symbols = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        rows = [{"SYMBOL": s.replace(".NS", "").replace(".BO", "").upper(),
                 "CLOSE": 0, "VOLUME": 0} for s in symbols]
        return pd.DataFrame(rows)
    except FileNotFoundError:
        return pd.DataFrame(columns=["SYMBOL", "CLOSE", "VOLUME"])


def fetch_nse_universe_with_meta():
    """
    Fetch full NSE equity universe with price + volume metadata.
    Tries last 4 calendar days to handle weekends/holidays.
    Returns DataFrame with columns: SYMBOL, CLOSE, VOLUME.
    """
    today = date.today()

    # Try today's cache first
    cache = _cache_path(today)
    if _is_fresh(cache):
        try:
            return pd.read_csv(cache)
        except Exception:
            pass

    # Try last 4 days (handles weekends + holidays)
    for delta in range(4):
        dt = today - timedelta(days=delta)
        day_cache = _cache_path(dt)
        if _is_fresh(day_cache, max_age_hours=48):
            try:
                return pd.read_csv(day_cache)
            except Exception:
                pass

        csv_text = _fetch_bhavcopy(dt)
        if csv_text:
            df = _parse_bhavcopy(csv_text)
            if df is not None and len(df) > 100:
                df.to_csv(day_cache, index=False)
                print(f"  NSE universe: {len(df)} stocks loaded from bhavcopy ({dt})")
                return df

    # Fallback
    print("  NSE bhavcopy unavailable — using nifty500.txt fallback")
    return _load_fallback()


def fetch_nse_universe():
    """
    Return list of NSE symbols with .NS suffix, filtered for liquidity.
    """
    df = fetch_nse_universe_with_meta()
    if df.empty:
        return []
    return [s + ".NS" for s in df["SYMBOL"].tolist()]
