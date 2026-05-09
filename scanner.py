"""
Earnings Momentum Scanner

Modes:
  weekly (default) — full NSE universe (~800 stocks), run on Saturdays
  daily            — sector + backbone stocks only, quick daily check

Usage:
  python scanner.py                          # weekly mode, top 30
  python scanner.py --mode daily --top 20
  python scanner.py --mode weekly --top 5 --min-score 35   # quick test
  python scanner.py --sector IT              # sector filter
"""

import sys
import os
import time
import argparse
import warnings
import pandas as pd
from datetime import date, timedelta

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.fetcher import fetch_cached, fetch_all_parallel
from data.earnings import fetch_earnings
from data.result_dates import get_result_date, fetch_upcoming_results
from data.sectors import rank_sectors, get_sector_stocks
from data.nse_universe import fetch_nse_universe
from engine.earnings_filter import filter_earnings
from engine.price_reactor import measure_reaction, avg_spike
from engine.entry_detector import detect_entry
from engine.profit_estimator import estimate_current_quarter
from engine.scorer import score_stock

RESULTS_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
BACKBONE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backbone50.txt")
os.makedirs(RESULTS_DIR, exist_ok=True)

POST_RESULT_WINDOW = 45
PRE_RESULT_WINDOW  = 30


def _load_list(path):
    try:
        with open(path) as f:
            return [l.strip() for l in f if l.strip() and not l.startswith("#")]
    except FileNotFoundError:
        return []


def _last_quarter_label(quarters):
    valid = [q for q in quarters if q.get("quarter")]
    return valid[-1]["quarter"] if valid else None


def _status_tag(mode, entry_info):
    if mode == "post" and entry_info and entry_info.get("rr", 0) >= 2.0:
        return "ENTER NOW"
    elif mode == "pre":
        return "WATCH"
    else:
        return "WATCH"


def _analyse_stock(symbol, df, sector_rank, upcoming_map, delay=1.0):
    """Full analysis pipeline for one stock. Returns result dict or None."""

    time.sleep(delay)  # rate limit screener.in

    quarters = fetch_earnings(symbol)
    if not quarters or len(quarters) < 4:
        return None

    ef = filter_earnings(quarters)
    if not ef["passes"]:
        return None

    if df is None or len(df) < 60:
        return None

    last_q      = _last_quarter_label(quarters)
    result_date = get_result_date(symbol, last_q, price_df=df) if last_q else None

    today      = date.today()
    mode       = None
    days_since = None
    days_until = None

    if result_date:
        delta = (today - result_date).days
        if 0 <= delta <= POST_RESULT_WINDOW:
            mode = "post"
            days_since = delta
        elif -PRE_RESULT_WINDOW <= delta < 0:
            mode = "pre"
            days_until = abs(delta)

    bare = symbol.replace(".NS", "").replace(".BO", "").upper()
    if mode is None and bare in upcoming_map:
        up_date   = upcoming_map[bare]
        delta_up  = (up_date - today).days
        if 0 <= delta_up <= PRE_RESULT_WINDOW:
            mode       = "pre"
            days_until = delta_up
            result_date = up_date

    if mode is None:
        return None

    # Historical reactions (last 4 quarters)
    valid_qs  = [q for q in quarters if q.get("quarter")]
    last4_qs  = valid_qs[-4:]
    reactions = []
    for q in last4_qs:
        rd = get_result_date(symbol, q["quarter"], price_df=df)
        if rd is None:
            continue
        rx = measure_reaction(symbol, rd, df)
        if rx:
            reactions.append(rx)

    # Entry detection (post-result only)
    entry_info = None
    if mode == "post" and result_date:
        spike_rx = measure_reaction(symbol, result_date, df)
        if spike_rx and spike_rx.get("spike_pct", 0) >= 2:
            entry_info = detect_entry(df, result_date, spike_rx["d0"])

    projection      = estimate_current_quarter(quarters)
    score_breakdown = score_stock(ef, reactions, entry_info, sector_rank)
    total_score     = score_breakdown["total"]
    cmp             = float(df["Close"].iloc[-1])

    return {
        "symbol":            symbol,
        "status":            _status_tag(mode, entry_info),
        "mode":              mode,
        "days_since_result": days_since,
        "days_to_result":    days_until,
        "last_quarter":      last_q,
        "result_date":       str(result_date) if result_date else None,
        "cmp":               round(cmp, 2),
        "entry":             entry_info["entry"]  if entry_info else None,
        "stop":              entry_info["stop"]   if entry_info else None,
        "target":            entry_info["target"] if entry_info else None,
        "rr":                entry_info["rr"]     if entry_info else None,
        "last_net_profit":   quarters[-1].get("net_profit"),
        "last_eps":          quarters[-1].get("eps"),
        "proj_profit":       projection["projected_net_profit"],
        "proj_eps":          projection["projected_eps"],
        "proj_yoy_growth":   projection["yoy_growth_pct"],
        "proj_confidence":   projection["confidence"],
        "avg_spike_pct":     avg_spike(reactions),
        "consistency_score": ef["consistency_score"],
        "avg_yoy_growth":    ef["avg_yoy_growth"],
        "growth_quarters":   ef["growth_quarters"],
        "sector_rank":       sector_rank,
        "score":             total_score,
    }


def _update_monthly_watchlist(df_new):
    """Append to monthly watchlist CSV, deduping by symbol (keep highest score)."""
    month_key  = date.today().strftime("%Y-%m")
    wl_path    = os.path.join(RESULTS_DIR, f"watchlist_{month_key}.csv")

    if os.path.exists(wl_path):
        try:
            df_existing = pd.read_csv(wl_path)
            combined    = pd.concat([df_existing, df_new], ignore_index=True)
            combined    = (
                combined
                .sort_values("score", ascending=False)
                .drop_duplicates(subset="symbol", keep="first")
                .reset_index(drop=True)
            )
        except Exception:
            combined = df_new
    else:
        combined = df_new

    combined.to_csv(wl_path, index=False)
    return wl_path


def main():
    parser = argparse.ArgumentParser(description="Earnings Momentum Scanner")
    parser.add_argument("--mode",      choices=["weekly", "daily"], default="weekly")
    parser.add_argument("--top",       type=int,   default=None)
    parser.add_argument("--min-score", type=float, default=None)
    parser.add_argument("--sector",    type=str,   default=None)
    parser.add_argument("--delay",     type=float, default=None,
                        help="Seconds between screener.in requests")
    parser.add_argument("--workers",   type=int,   default=None,
                        help="Parallel workers for price fetch")
    args = parser.parse_args()

    # Mode-based defaults
    if args.mode == "weekly":
        top       = args.top       or 30
        min_score = args.min_score or 35
        delay     = args.delay     or 2.0
        workers   = args.workers   or 5
    else:
        top       = args.top       or 20
        min_score = args.min_score or 40
        delay     = args.delay     or 1.0
        workers   = args.workers   or 10

    print("=" * 65)
    print("  EARNINGS MOMENTUM SCANNER")
    print(f"  Mode: {args.mode.upper()}   Date: {date.today()}")
    print("=" * 65)

    # ── Step 1: Sector ranking ──
    print("\n[1/4] Ranking sectors...")
    try:
        ranked_sectors = rank_sectors()
        for s in ranked_sectors[:5]:
            arrow = "+" if s["ret_20d"] > 0 else "-"
            print(f"  #{s['rank']} {s['sector']:<16} 20d={s['ret_20d']:+.1f}%  "
                  f"5d={s['ret_5d']:+.1f}%  [{arrow}]")
    except Exception as e:
        print(f"  Sector ranking failed: {e}")
        ranked_sectors = []

    # ── Step 2: Build symbol list ──
    print("\n[2/4] Building stock universe...")
    sector_stock_map = {}

    if args.sector:
        for sym in get_sector_stocks(args.sector):
            sector_stock_map[sym] = 1
        print(f"  Sector filter: {args.sector} ({len(sector_stock_map)} stocks)")

    elif args.mode == "weekly":
        universe = fetch_nse_universe()
        for sym in universe:
            sector_stock_map[sym] = 99
        # Backbone always included
        for sym in _load_list(BACKBONE_FILE):
            sector_stock_map.setdefault(sym, 99)
        print(f"  Full NSE universe: {len(sector_stock_map)} stocks")

    else:
        # Daily: sector stocks + backbone
        top4 = ranked_sectors[:4] if ranked_sectors else []
        for s in top4:
            for sym in get_sector_stocks(s["sector"]):
                sector_stock_map.setdefault(sym, s["rank"])
        for sym in _load_list(BACKBONE_FILE):
            sector_stock_map.setdefault(sym, 99)
        print(f"  Daily universe: {len(sector_stock_map)} stocks")

    all_symbols = list(sector_stock_map.keys())

    # ── Step 3: Upcoming results ──
    print("\n[3/4] Fetching upcoming result dates...")
    try:
        upcoming     = fetch_upcoming_results(days_ahead=PRE_RESULT_WINDOW)
        upcoming_map = {u["symbol"]: u["result_date"] for u in upcoming}
        print(f"  {len(upcoming)} results expected in next {PRE_RESULT_WINDOW} days")
    except Exception as e:
        print(f"  Could not fetch upcoming results: {e}")
        upcoming_map = {}

    # ── Step 4: Fetch price data ──
    print(f"\n[4/4] Fetching price data ({workers} workers)...")
    price_data = fetch_all_parallel(all_symbols, days=800, max_workers=workers)

    # ── Step 5: Scan ──
    print(f"\nScanning {len(all_symbols)} stocks "
          f"(delay={delay}s between earnings requests)...\n")

    results     = []
    total       = len(all_symbols)
    scanned     = 0

    for sym in all_symbols:
        scanned += 1
        print(f"  [{scanned:>4}/{total}] {sym:<20}", end=" ", flush=True)
        try:
            df          = price_data.get(sym)
            sector_rank = sector_stock_map.get(sym, 99)
            res         = _analyse_stock(sym, df, sector_rank, upcoming_map, delay=delay)
            if res and res["score"] >= min_score:
                results.append(res)
                tag = res["status"]
                print(f"  [{tag}] score={res['score']} | rr={res['rr']} | "
                      f"yoy={res['proj_yoy_growth']}%")
            else:
                print("skip")
        except Exception as e:
            print(f"err: {e}")

    # ── Summary block ──
    post_count   = sum(1 for r in results if r["mode"] == "post")
    pre_count    = sum(1 for r in results if r["mode"] == "pre")
    enter_count  = sum(1 for r in results if r["status"] == "ENTER NOW")
    top_score    = max((r["score"] for r in results), default=0)
    top_sym      = next((r["symbol"] for r in results if r["score"] == top_score), "-")

    print(f"\n{'=' * 65}")
    print(f"  SCAN COMPLETE — {date.today()}")
    print(f"  Stocks scanned  : {total}")
    print(f"  Passed filter   : {len(results)}")
    print(f"  POST-result     : {post_count}  (entry window open)")
    print(f"  PRE-result      : {pre_count}  (watch for result)")
    print(f"  ENTER NOW       : {enter_count}  (RR >= 2.0, pullback entry ready)")
    print(f"  Top score       : {top_score} ({top_sym})")
    print(f"{'=' * 65}")

    if not results:
        print("\n  No setups found. Try lowering --min-score.")
        return

    df_out   = pd.DataFrame(results).sort_values("score", ascending=False).head(top)
    out_path = os.path.join(RESULTS_DIR, f"scanner_{date.today()}.csv")
    df_out.to_csv(out_path, index=False)

    # Monthly watchlist (weekly mode only)
    wl_path = None
    if args.mode == "weekly":
        wl_path = _update_monthly_watchlist(df_out)

    # ── Results table ──
    print(f"\n  TOP {len(df_out)} SETUPS")
    print(f"  {'Symbol':<18} {'Status':<11} {'Score':>5} {'Entry':>8} "
          f"{'Stop':>8} {'Target':>8} {'RR':>5} {'YoY%':>7} {'Conf':<6}")
    print("  " + "-" * 80)
    for _, row in df_out.iterrows():
        print(
            f"  {row['symbol']:<18} {row['status']:<11} {row['score']:>5} "
            f"{str(row['entry'] or '-'):>8} {str(row['stop'] or '-'):>8} "
            f"{str(row['target'] or '-'):>8} {str(row['rr'] or '-'):>5} "
            f"{str(row['proj_yoy_growth'] or '-'):>7} "
            f"{str(row['proj_confidence'] or '-'):<6}"
        )

    print(f"\n  Scan saved to   : {out_path}")
    if wl_path:
        print(f"  Monthly watchlist: {wl_path}")
    print(f"{'=' * 65}\n")


if __name__ == "__main__":
    main()
