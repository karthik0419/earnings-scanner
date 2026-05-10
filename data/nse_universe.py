"""
NSE sector-based universe fetcher.
Pulls official index constituent lists from niftyindices.com for all
18 sector/thematic indices. Covers ~400-500 quality, liquid stocks
across every sector — no stock left behind.

Sector momentum is used for SCORING only, not filtering.
All sectors scanned every week.
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from io import StringIO

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache")
BASE_DIR  = os.path.join(os.path.dirname(__file__), "..")
os.makedirs(CACHE_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Referer": "https://www.niftyindices.com/",
}

# All NSE sector + thematic indices with their constituent file names
# Source: https://www.niftyindices.com/IndexConstituent/
INDEX_UNIVERSE = {
    # Broad market
    "Nifty 50":          "ind_nifty50list.csv",
    "Nifty Next 50":     "ind_niftynext50list.csv",
    "Nifty Midcap 150":  "ind_niftymidcap150list.csv",
    "Nifty Smallcap 100":"ind_niftysmallcap100list.csv",

    # Sector indices
    "IT":                "ind_niftyitlist.csv",
    "Bank":              "ind_niftybanklist.csv",
    "Pharma":            "ind_niftypharmalist.csv",
    "Auto":              "ind_niftyautolist.csv",
    "FMCG":              "ind_niftyfmcglist.csv",
    "Metal":             "ind_niftymetallist.csv",
    "Realty":            "ind_niftyrealtylist.csv",
    "Energy":            "ind_niftyenergylist.csv",
    "Media":             "ind_niftymedialist.csv",
    "PSU Bank":          "ind_niftypsubanklist.csv",
    "Private Bank":      "ind_niftypvtbanklist.csv",
    "Financial Services":"ind_niftyfinancelist.csv",
    "Healthcare":        "ind_niftyhealthcarelist.csv",
    "Consumption":       "ind_niftyconsumptionlist.csv",

    # Thematic indices
    "Infra":             "ind_niftyinfralist.csv",
    "PSE":               "ind_niftycpselist.csv",
    "MNC":               "ind_niftymnclist.csv",
    "Oil & Gas":         "ind_niftyoilgaslist.csv",
    "Commodities":       "ind_niftycommoditieslist.csv",
}

# Defense stocks hardcoded — Nifty India Defence index not downloadable
DEFENSE_STOCKS = [
    "HAL", "BEL", "BEML", "MTAR", "DCXSYS", "PARASDEF",
    "GRSE", "MAZDOCK", "BDL", "COCHINSHIP", "SOLARINDS",
    "ASTRAMICRO", "DATAPATTNS", "MIDHANI", "AIALIMITED",
]

BASE_URL = "https://www.niftyindices.com/IndexConstituent/"

CACHE_FILE = os.path.join(CACHE_DIR, "sector_universe.csv")


def _is_fresh(path, max_age_hours=72):
    if not os.path.exists(path):
        return False
    age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(path))
    return age < timedelta(hours=max_age_hours)


def _fetch_index_constituents(filename):
    """Fetch one index constituent CSV from niftyindices.com."""
    url = BASE_URL + filename
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200 and len(resp.content) > 100:
            return resp.text
    except Exception:
        pass
    return None


def _parse_constituents(csv_text, sector_name):
    """
    Parse constituent CSV. Columns vary but always include Symbol.
    Returns list of dicts with symbol + sector.
    """
    try:
        df = pd.read_csv(StringIO(csv_text))
        df.columns = [c.strip() for c in df.columns]

        # Find symbol column — NSE uses "Symbol" consistently
        sym_col = None
        for c in df.columns:
            if c.strip().lower() == "symbol":
                sym_col = c
                break

        if sym_col is None:
            return []

        symbols = df[sym_col].dropna().str.strip().tolist()
        return [{"symbol": s, "sector": sector_name} for s in symbols if s]

    except Exception:
        return []


def fetch_sector_universe():
    """
    Fetch all sector index constituents and return combined DataFrame.
    Columns: symbol (bare NSE), sector, symbol_ns (.NS suffix)
    Cached for 72 hours.
    """
    if _is_fresh(CACHE_FILE):
        try:
            df = pd.read_csv(CACHE_FILE)
            if len(df) > 100:
                return df
        except Exception:
            pass

    all_stocks = []
    print(f"  Fetching {len(INDEX_UNIVERSE)} sector indices from niftyindices.com...")

    for sector, filename in INDEX_UNIVERSE.items():
        csv_text = _fetch_index_constituents(filename)
        if csv_text:
            stocks = _parse_constituents(csv_text, sector)
            print(f"    {sector:<22} {len(stocks)} stocks")
            all_stocks.extend(stocks)
        else:
            print(f"    {sector:<22} unavailable")
        time.sleep(0.3)  # polite delay

    if not all_stocks:
        print("  All sector fetches failed — using nifty500.txt fallback")
        return _load_fallback()

    # Add Defense stocks manually
    for s in DEFENSE_STOCKS:
        all_stocks.append({"symbol": s, "sector": "Defense"})
    print(f"    {'Defense':<22} {len(DEFENSE_STOCKS)} stocks (hardcoded)")

    df = pd.DataFrame(all_stocks)

    # Deduplicate — keep first occurrence (broad indices first, then sectors)
    df = df.drop_duplicates(subset="symbol", keep="first").reset_index(drop=True)
    df["symbol_ns"] = df["symbol"] + ".NS"

    df.to_csv(CACHE_FILE, index=False)
    print(f"\n  Total unique stocks: {len(df)} across all indices")
    return df


def fetch_nse_universe():
    """Return list of symbols with .NS suffix from all sector indices."""
    df = fetch_sector_universe()
    if df.empty:
        return []
    col = "symbol_ns" if "symbol_ns" in df.columns else "symbol"
    syms = df[col].tolist()
    return [s if s.endswith(".NS") else s + ".NS" for s in syms]


def get_symbol_sector_map():
    """Return dict {symbol.NS: sector} for scoring."""
    df = fetch_sector_universe()
    if df.empty:
        return {}
    col = "symbol_ns" if "symbol_ns" in df.columns else "symbol"
    result = {}
    for _, row in df.iterrows():
        sym = row[col]
        if not sym.endswith(".NS"):
            sym += ".NS"
        result[sym] = row["sector"]
    return result


def _load_fallback():
    """Load nifty500.txt as fallback."""
    path = os.path.join(BASE_DIR, "nifty500.txt")
    rows = []
    try:
        with open(path) as f:
            for line in f:
                s = line.strip()
                if s and not s.startswith("#"):
                    bare = s.replace(".NS", "").replace(".BO", "").upper()
                    rows.append({"symbol": bare, "sector": "Nifty 500", "symbol_ns": bare + ".NS"})
    except FileNotFoundError:
        pass
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["symbol", "sector", "symbol_ns"])
