"""
NSE sector ranker using yfinance sector index data.
Ranks sectors by recent momentum (20-day + 5-day return + MA20).
"""

import warnings
warnings.filterwarnings("ignore")

import yfinance as yf
import pandas as pd

# NSE sector indices on Yahoo Finance
SECTOR_INDICES = {
    "IT":       "^CNXIT",
    "Bank":     "^NSEBANK",
    "Pharma":   "^CNXPHARMA",
    "Auto":     "^CNXAUTO",
    "FMCG":     "^CNXFMCG",
    "Metal":    "^CNXMETAL",
    "Realty":   "^CNXREALTY",
    "Infra":    "^CNXINFRA",
    "Energy":   "^CNXENERGY",
    "Media":    "^CNXMEDIA",
    "PSU Bank": "^CNXPSUBANK",
}

# Top stocks per sector (NSE symbols with .NS suffix)
SECTOR_STOCKS = {
    "IT": [
        "TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS",
        "LTIM.NS", "MPHASIS.NS", "COFORGE.NS", "PERSISTENT.NS", "OFSS.NS",
        "HEXAWARE.NS", "KPITTECH.NS", "LTTS.NS", "TATAELXSI.NS", "NIIT.NS",
    ],
    "Bank": [
        "HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS", "SBIN.NS",
        "INDUSINDBK.NS", "BANDHANBNK.NS", "FEDERALBNK.NS", "IDFCFIRSTB.NS", "RBLBANK.NS",
        "AUBANK.NS", "CSBBANK.NS", "DCBBANK.NS", "KARNATAKA.NS", "EQUITASBNK.NS",
    ],
    "Pharma": [
        "SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "LUPIN.NS",
        "AUROPHARMA.NS", "TORNTPHARM.NS", "ALKEM.NS", "IPCA.NS", "GRANULES.NS",
        "LAURUSLABS.NS", "NATCOPHARM.NS", "GLAND.NS", "ABBOTINDIA.NS", "PFIZER.NS",
    ],
    "Auto": [
        "MARUTI.NS", "TATAMOTORS.NS", "M&M.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS",
        "EICHERMOT.NS", "TVSMOTOR.NS", "ASHOKLEY.NS", "MOTHERSON.NS", "BHARATFORG.NS",
        "BOSCHLTD.NS", "EXIDEIND.NS", "AMARA RAJA.NS", "BALKRISIND.NS", "MRF.NS",
    ],
    "FMCG": [
        "HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "DABUR.NS",
        "MARICO.NS", "COLPAL.NS", "GODREJCP.NS", "EMAMILTD.NS", "TATACONSUM.NS",
        "VBL.NS", "RADICO.NS", "UBL.NS", "MCDOWELL-N.NS", "PGHH.NS",
    ],
    "Metal": [
        "TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "SAIL.NS", "VEDL.NS",
        "NMDC.NS", "COALINDIA.NS", "NATIONALUM.NS", "JINDALSTEL.NS", "APLAPOLLO.NS",
        "RATNAMANI.NS", "WELSPUNLIV.NS", "TIINDIA.NS", "GMRAIRPORT.NS", "HFCL.NS",
    ],
    "Realty": [
        "DLF.NS", "GODREJPROP.NS", "OBEROIRLTY.NS", "PRESTIGE.NS", "PHOENIXLTD.NS",
        "BRIGADE.NS", "SOBHA.NS", "MAHLIFE.NS", "KOLTEPATIL.NS", "SUNTECK.NS",
        "LODHA.NS", "SIGNATURE.NS", "ARVIND.NS", "ANANTRAJ.NS", "IBREALEST.NS",
    ],
    "Infra": [
        "LT.NS", "ADANIPORTS.NS", "GMRAIRPORT.NS", "IRB.NS", "ASHOKA.NS",
        "KNR.NS", "PNC.NS", "SADBHAV.NS", "HGINFRA.NS", "GPPL.NS",
        "SIEMENS.NS", "ABB.NS", "THERMAX.NS", "CUMMINSIND.NS", "BHEL.NS",
    ],
    "Energy": [
        "RELIANCE.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "BPCL.NS",
        "IOC.NS", "HPCL.NS", "GAIL.NS", "ADANIGREEN.NS", "TATAPOWER.NS",
        "TORNTPOWER.NS", "CESC.NS", "PETRONET.NS", "IGL.NS", "MGL.NS",
    ],
    "Media": [
        "ZEEL.NS", "SUNTV.NS", "PVRINOX.NS", "NETWORK18.NS", "TV18BRDCST.NS",
        "TVTODAY.NS", "NDTV.NS", "SAREGAMA.NS", "TIPS.NS", "EROS.NS",
    ],
    "PSU Bank": [
        "SBIN.NS", "BANKBARODA.NS", "PNB.NS", "CANBK.NS", "UNIONBANK.NS",
        "INDIANB.NS", "BANKINDIA.NS", "IOB.NS", "UCOBANK.NS", "CENTRALBK.NS",
    ],
    "Private Bank": [
        "HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS", "INDUSINDBK.NS",
        "BANDHANBNK.NS", "FEDERALBNK.NS", "IDFCFIRSTB.NS", "RBLBANK.NS", "AUBANK.NS",
    ],
    "Consumption": [
        "HINDUNILVR.NS", "ITC.NS", "TITAN.NS", "TRENT.NS", "DMART.NS",
        "PAGEIND.NS", "ABFRL.NS", "VEDANT.NS", "MANYAVAR.NS", "SHOPERSTOP.NS",
        "BATA.NS", "RELAXO.NS", "CAMPUS.NS", "METRO.NS", "KALYANKJIL.NS",
    ],
}


def rank_sectors():
    """
    Rank NSE sectors by recent momentum.
    Returns list of dicts sorted best to worst.
    """
    ranked = []

    for sector, yf_symbol in SECTOR_INDICES.items():
        try:
            df = yf.download(yf_symbol, period="3mo", interval="1d", progress=False, auto_adjust=True)
            if df is None or len(df) < 25:
                continue

            closes = df["Close"].dropna()
            if len(closes) < 25:
                continue

            cmp = float(closes.iloc[-1])
            ret_20d = float((closes.iloc[-1] - closes.iloc[-21]) / closes.iloc[-21] * 100) if len(closes) >= 21 else 0
            ret_5d  = float((closes.iloc[-1] - closes.iloc[-6]) / closes.iloc[-6] * 100) if len(closes) >= 6 else 0
            ma20 = float(closes.tail(20).mean())

            score = ret_20d * 0.6 + ret_5d * 0.4
            if cmp > ma20:
                score += 5

            ranked.append({
                "sector":   sector,
                "symbol":   yf_symbol,
                "ret_20d":  round(ret_20d, 2),
                "ret_5d":   round(ret_5d, 2),
                "above_ma20": cmp > ma20,
                "score":    round(score, 2),
            })
        except Exception:
            continue

    ranked.sort(key=lambda x: x["score"], reverse=True)
    for i, s in enumerate(ranked):
        s["rank"] = i + 1

    return ranked


def get_sector_stocks(sector_name):
    """Return stock symbols for a given sector name."""
    return SECTOR_STOCKS.get(sector_name, [])


def get_top_sector_stocks(top_n=4):
    """Rank sectors and return stocks from the top N sectors."""
    ranked = rank_sectors()
    top_sectors = ranked[:top_n]
    stocks = []
    seen = set()
    for s in top_sectors:
        for sym in get_sector_stocks(s["sector"]):
            if sym not in seen:
                stocks.append(sym)
                seen.add(sym)
    return stocks, top_sectors
