"""
NSE sector-based universe fetcher.
Pulls official index constituent lists from niftyindices.com for all
major sector/thematic indices. Additional sectors hardcoded where
niftyindices.com does not expose downloadable CSVs.

Covers ~550+ quality stocks across ALL NSE equity sectors.
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

    # Additional thematic — try CSV; supplemented by hardcoded if unavailable
    "Capital Market":    "ind_niftycapitalmarketlist.csv",
    "India Manufacturing":"ind_niftyindiamanufacturinglist.csv",
    "Services Sector":   "ind_niftyservicesectorlist.csv",
}

# Sectors hardcoded where niftyindices.com does not expose a downloadable CSV.
# These supplement the index-fetched lists; deduplication handles any overlap.
HARDCODED_SECTORS = {

    # Nifty India Defence — CSV not available on niftyindices.com
    "Defense": [
        "HAL", "BEL", "BEML", "MTARTECH", "DCX", "PARASDEF",
        "GRSE", "MAZDOCK", "BDL", "COCHINSHIP", "SOLARINDS",
        "ASTRAMICRO", "DATAPATTNS", "MIDHANI",
        # MTAR→MTARTECH, DCXSYS→DCX, AIALIMITED removed (unlisted)
    ],

    # Chemicals — specialty, agro, commodity chemicals
    "Chemicals": [
        "PIDILITIND", "AARTIIND", "DEEPAKFERT", "GNFC", "TATACHEM",
        "VINATIORGA", "IOLCP", "NAVINFLUOR", "ALKYLAMINE", "FINEORG",
        "CLEAN", "GUJALKALI", "PCBL", "SUDARSCHEM", "DEEPAKNTR",
        "SRF", "NOCIL", "SOLARA", "ASTEC", "BASF",
        "GHCL", "UFLEX", "NEOGENECHEM", "ROSSARI",
        # AARTI removed (dup of AARTIIND), NEOGEN→NEOGENECHEM
    ],

    # Capital Markets — exchanges, depositories, AMCs, brokers
    "Capital Markets": [
        "MCX", "CDSL", "BSE", "ANGELONE", "KFINTECH",
        "CAMS", "MOTILALOFS", "IIFLSEC", "NUVAMA", "CHOICEIN",
        "GEOJITFSL", "ICICIPRULI", "HDFCLIFE", "SBILIFE",
        "360ONE", "ICICIGI", "BAJAJFINSV",
        # MCXINDIA→MCX, MOTILALOSW→MOTILALOFS
    ],

    # EV & New Age Automotive — EVs, auto components, charging
    "EV & New Age Auto": [
        "OLECTRA", "TIINDIA", "WARDWIZARD", "EXIDEIND", "AMARAJABAT",
        "TATAELXSI", "KAYNES", "SONACOMS", "CRAFTSMAN", "SANSERA",
        "SUPRAJIT", "GABRIEL", "ENDURANCE", "MOTHERSON", "BOSCHLTD",
        # AMARARAJA→AMARAJABAT
    ],

    # New Age / Digital Tech — platform companies, SaaS, fintechs
    "New Age Tech": [
        "ZOMATO", "NYKAA", "POLICYBZR", "DELHIVERY", "CARTRADE",
        "EASEMYTRIP", "MAPMYINDIA", "LATENTVIEW", "TANLA",
        "ROUTE", "INTELLECT", "NEWGEN", "MASTEK", "TATATECH",
        "ZAGGLE", "RATEGAIN", "INDIASHLTR",
    ],

    # Textiles — apparel, yarn, home furnishing
    "Textiles": [
        "PAGEIND", "VARDHACRL", "WELSPUNLIV", "RAYMOND", "TRIDENT",
        "KITEX", "ALOKINDS", "FILATEX", "GRASIM", "ARVIND",
        "RUPA", "DOLLAR", "NITINSPIN", "SPORTKING",
        # VARDHMAN→VARDHACRL, ALOKTEXT→ALOKINDS, NITIN→NITINSPIN, ICIL removed
    ],

    # Agri & Fertilizers — crop protection, agri inputs
    "Agri & Fertilizers": [
        "COROMANDEL", "PIIND", "CHAMBLFERT", "GSFC",
        "DEEPAKFERT", "RALLIS", "DHANUKA", "BAYERCROP",
        "ASTEC", "INSECTICIDES", "EXCELINDUS",
        "KSCL", "SUMICHEM",
        # CHAMBAL→CHAMBLFERT, BAYER→BAYERCROP, SUMITCHEM→SUMICHEM
        # INSECTICID→INSECTICIDES, EXCEL→EXCELINDUS, DHARAMSI/SAHYADRI removed
    ],

    # Logistics — freight, courier, 3PL, rail
    "Logistics": [
        "DELHIVERY", "CONCOR", "BLUEDART", "GATI", "ALLCARGO",
        "MAHLOG", "TCI", "TVSSCS", "VRLLOG", "APLAPOLLO",
        # MAHINDLOG→MAHLOG, VRL→VRLLOG, XPRESSBEES/GATIFLEX removed (unlisted)
    ],

    # Power — generation, distribution, transmission
    "Power": [
        "TATAPOWER", "TORNTPOWER", "ADANIPOWER", "CESC",
        "JPPOWER", "NHPC", "SJVN", "GIPCL", "KALPATPOWR",
        "RTNPOWER", "JSWENERGY", "INOXWIND", "SUZLON",
        # WINDWORLD/GREENKO removed (unlisted/private)
    ],

    # Telecom — operators, equipment, cables, networking
    "Telecom": [
        "BHARTIARTL", "IDEA", "HFCL", "STLTECH", "TEJASNET",
        "VINDHYATEL", "RAILTEL", "ITI", "TATACOMM",
        "OPTIEMUS", "CMSINFO",
    ],
}

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
        # Filter out dummy/placeholder rows niftyindices.com injects in some CSVs
        return [
            {"symbol": s, "sector": sector_name}
            for s in symbols
            if s and not s.upper().startswith("DUMMY") and len(s) <= 20
        ]

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

    # Add all hardcoded sector stocks
    for sector_name, stocks in HARDCODED_SECTORS.items():
        for s in stocks:
            all_stocks.append({"symbol": s, "sector": sector_name})
        print(f"    {sector_name:<22} {len(stocks)} stocks (hardcoded)")

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
