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
MIN_VOLUME = 10000    # minimum daily traded quantity


def _cache_path(dt):
    return os.path.join(CACHE_DIR, f"nse_universe_{dt}.csv")


def _is_fresh(path, max_age_hours=24):
    if not os.path.exists(path):
        return False
    age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(path))
    return age < timedelta(hours=max_age_hours)


def _fetch_equity_master():
    """
    Fetch NSE equity master list — all listed EQ stocks.
    URL: https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv
    This is a static file, no session/cookie needed.
    """
    url = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
    try:
        resp = requests.get(url, headers=NSE_HEADERS, timeout=20)
        if resp.status_code == 200 and len(resp.content) > 1000:
            return resp.text
    except Exception:
        pass
    return None


def _fetch_bhavcopy(dt):
    """Try to download NSE bhavcopy for a given date."""
    session = requests.Session()
    session.headers.update(NSE_HEADERS)

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


def _parse_equity_master(csv_text):
    """Parse NSE equity master CSV — returns DataFrame with SYMBOL, CLOSE, VOLUME."""
    from io import StringIO
    try:
        df = pd.read_csv(StringIO(csv_text))
        df.columns = [c.strip() for c in df.columns]

        # Equity master columns: SYMBOL, NAME OF COMPANY, SERIES, DATE OF LISTING, etc.
        if "SYMBOL" not in df.columns:
            return None

        df["SYMBOL"] = df["SYMBOL"].str.strip()

        # Filter EQ series only if column exists
        if "SERIES" in df.columns:
            df = df[df["SERIES"].str.strip() == "EQ"]

        # No price/volume in master list — set dummy values (price filter applied later via price data)
        df["CLOSE"]  = 0
        df["VOLUME"] = 0

        return df[["SYMBOL", "CLOSE", "VOLUME"]].drop_duplicates("SYMBOL").reset_index(drop=True)
    except Exception:
        return None


def fetch_nse_universe_with_meta():
    """
    Fetch full NSE equity universe.
    Priority:
      1. Cached bhavcopy (has price+volume for filtering)
      2. NSE equity master list (all listed stocks, no price filter)
      3. Bhavcopy from last 4 trading days
      4. nifty500.txt fallback
    Returns DataFrame with columns: SYMBOL, CLOSE, VOLUME.
    """
    today = date.today()

    # Try cached bhavcopy first
    for delta in range(5):
        dt        = today - timedelta(days=delta)
        day_cache = _cache_path(dt)
        if _is_fresh(day_cache, max_age_hours=72):
            try:
                df = pd.read_csv(day_cache)
                if len(df) > 200:
                    return df
            except Exception:
                pass

    # Try equity master list (no auth needed, always available)
    master_cache = os.path.join(CACHE_DIR, "nse_equity_master.csv")
    if _is_fresh(master_cache, max_age_hours=72):
        try:
            df = pd.read_csv(master_cache)
            if len(df) > 200:
                print(f"  NSE universe: {len(df)} stocks from equity master (cached)")
                return df
        except Exception:
            pass

    csv_text = _fetch_equity_master()
    if csv_text:
        df = _parse_equity_master(csv_text)
        if df is not None and len(df) > 200:
            df.to_csv(master_cache, index=False)
            print(f"  NSE universe: {len(df)} stocks from equity master list")
            return df

    # Try fresh bhavcopy for last 4 trading days
    for delta in range(4):
        dt       = today - timedelta(days=delta)
        csv_text = _fetch_bhavcopy(dt)
        if csv_text:
            df = _parse_bhavcopy(csv_text)
            if df is not None and len(df) > 100:
                df.to_csv(_cache_path(dt), index=False)
                print(f"  NSE universe: {len(df)} stocks from bhavcopy ({dt})")
                return df

    print("  NSE sources unavailable — using nifty500.txt fallback")
    return _load_fallback()


def fetch_nse_universe():
    """
    Return list of NSE symbols with .NS suffix, filtered for liquidity.
    """
    df = fetch_nse_universe_with_meta()
    if df.empty:
        return []
    return [s + ".NS" for s in df["SYMBOL"].tolist()]
