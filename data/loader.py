import os
import pandas as pd
from datetime import date, timedelta

# Fix jugaad-data Windows makedirs bug
_orig_makedirs = os.makedirs
os.makedirs = lambda p, *a, **kw: _orig_makedirs(p, *a, exist_ok=True, **{k: v for k, v in kw.items() if k != "exist_ok"})

from jugaad_data.nse import stock_df as nse_stock_df


def _nse_symbol(symbol):
    return symbol.replace(".NS", "").replace(".BO", "").upper()


def _fetch_nse(symbol, days=180):
    sym = _nse_symbol(symbol)
    to_dt = date.today()
    from_dt = to_dt - timedelta(days=days)
    raw = None
    try:
        raw = nse_stock_df(symbol=sym, from_date=from_dt, to_date=to_dt, series="EQ")
    except Exception as e:
        print(f"  [NSE] fetch failed for {sym}: {e}")

    if raw is not None and not raw.empty:
        raw = raw.rename(columns={
            "DATE": "Date", "OPEN": "Open", "HIGH": "High",
            "LOW": "Low", "CLOSE": "Close", "VOLUME": "Volume",
        })
        raw["Date"] = pd.to_datetime(raw["Date"]).dt.tz_localize(None).dt.normalize()
        raw = raw.set_index("Date").sort_index()
        cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in raw.columns]
        return raw[cols].dropna()

    # Fallback: yfinance
    try:
        import yfinance as yf
        yf_sym = symbol if symbol.endswith(".NS") else sym + ".NS"
        period_map = {180: "6mo", 400: "2y", 600: "3y", 800: "4y"}
        period = period_map.get(days) or ("2y" if days <= 400 else "5y")
        df = yf.download(yf_sym, period=period, interval="1d", progress=False, auto_adjust=True)
        if df is not None and not df.empty:
            df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
            df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
            return df
    except Exception:
        pass

    return None


def _resample_weekly(df_daily):
    return (
        df_daily.resample("W")
        .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
        .dropna()
    )
