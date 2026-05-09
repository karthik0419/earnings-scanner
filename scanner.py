"""
Earnings Momentum Scanner — daily runner.

Workflow:
  1. Rank sectors → pick top 4 booming sectors
  2. Collect stocks from top sectors + backbone
  3. For each stock:
     a. Fetch quarterly earnings from screener.in
     b. Filter by earnings consistency (3+ quarters of growth)
     c. Fetch price data
     d. Check: post-result (within 20 days) → find pullback entry
               pre-result (within 30 days)  → flag as WATCH with projected profit
     e. Score the stock
  4. Sort by score, output top N
  5. Save to results/scanner_{date}.csv

Usage:
  python scanner.py
  python scanner.py --top 20 --min-score 40
  python scanner.py --sector IT --top 15
"""

import sys
import os
import argparse
import warnings
import pandas as pd
from datetime import date, timedelta

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.fetcher import fetch_cached, fetch_all_parallel
from data.earnings import fetch_earnings
from data.result_dates import get_result_date, fetch_upcoming_results
from data.sectors import rank_sectors, get_top_sector_stocks, get_sector_stocks, SECTOR_STOCKS
from engine.earnings_filter import filter_earnings
from engine.price_reactor import measure_reaction, avg_spike
from engine.entry_detector import detect_entry
from engine.profit_estimator import estimate_current_quarter
from engine.scorer import score_stock

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

BACKBONE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backbone50.txt")
POST_RESULT_WINDOW = 45   # days after result to look for pullback entry
PRE_RESULT_WINDOW  = 30   # days before result to flag as watch


def _load_list(path):
    try:
        with open(path) as f:
            return [l.strip() for l in f if l.strip() and not l.startswith("#")]
    except FileNotFoundError:
        return []


def _last_quarter_label(quarters):
    valid = [q for q in quarters if q.get("quarter")]
    return valid[-1]["quarter"] if valid else None


def _analyse_stock(symbol, df, sector_rank, upcoming_map):
    """Full analysis pipeline for one stock. Returns result dict or None."""

    # 1. Fetch earnings
    quarters = fetch_earnings(symbol)
    if not quarters or len(quarters) < 4:
        return None

    # 2. Earnings filter
    ef = filter_earnings(quarters)
    if not ef["passes"]:
        return None

    # 3. Price data check
    if df is None or len(df) < 60:
        return None

    # 4. Determine mode: post-result or pre-result
    last_q = _last_quarter_label(quarters)
    result_date = get_result_date(symbol, last_q, price_df=df) if last_q else None

    today = date.today()
    mode = None
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

    # Check upcoming results map for pre-result stocks not caught above
    bare = symbol.replace(".NS", "").replace(".BO", "").upper()
    if mode is None and bare in upcoming_map:
        up_date = upcoming_map[bare]
        delta_up = (up_date - today).days
        if 0 <= delta_up <= PRE_RESULT_WINDOW:
            mode = "pre"
            days_until = delta_up
            result_date = up_date

    if mode is None:
        return None  # stock not in any active window

    # 5. Historical reaction across last 4 quarters
    valid_qs = [q for q in quarters if q.get("quarter")]
    last4_qs  = valid_qs[-4:]
    reactions  = []
    for q in last4_qs:
        rd = get_result_date(symbol, q["quarter"])
        if rd is None:
            continue
        rx = measure_reaction(symbol, rd, df)
        if rx:
            reactions.append(rx)

    # 6. Entry detection (post-result only)
    entry_info = None
    if mode == "post" and result_date:
        spike_rx = measure_reaction(symbol, result_date, df)
        if spike_rx and spike_rx.get("spike_pct", 0) >= 2:
            entry_info = detect_entry(df, result_date, spike_rx["d0"])

    # 7. Profit projection
    projection = estimate_current_quarter(quarters)

    # 8. Score
    score_breakdown = score_stock(ef, reactions, entry_info, sector_rank)
    total_score = score_breakdown["total"]

    cmp = float(df["Close"].iloc[-1])
    last_profit = quarters[-1].get("net_profit")
    last_eps    = quarters[-1].get("eps")

    return {
        "symbol":            symbol,
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
        "last_net_profit":   last_profit,
        "last_eps":          last_eps,
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
        "score_breakdown":   str(score_breakdown),
    }


def main():
    parser = argparse.ArgumentParser(description="Earnings Momentum Scanner")
    parser.add_argument("--top",       type=int,   default=20)
    parser.add_argument("--min-score", type=float, default=40)
    parser.add_argument("--sector",    type=str,   default=None,
                        help="Filter to a specific sector e.g. IT, Bank, Pharma")
    args = parser.parse_args()

    print("=" * 65)
    print("  SWING SCANNER V3 — EARNINGS MOMENTUM")
    print(f"  {date.today()}")
    print("=" * 65)

    # ── Step 1: Sector ranking ──
    print("\n[1/4] Ranking sectors...")
    try:
        ranked_sectors = rank_sectors()
        print("  Top sectors today:")
        for s in ranked_sectors[:6]:
            arrow = "▲" if s["ret_20d"] > 0 else "▼"
            print(f"    #{s['rank']} {s['sector']:<16} 20d={s['ret_20d']:+.1f}%  5d={s['ret_5d']:+.1f}%  {arrow}")
    except Exception as e:
        print(f"  Sector ranking failed: {e}. Proceeding with backbone only.")
        ranked_sectors = []

    # ── Step 2: Build symbol list ──
    print("\n[2/4] Building stock universe...")
    backbone = _load_list(BACKBONE_FILE)
    sector_stock_map = {}  # symbol -> sector_rank

    if args.sector:
        sector_syms = get_sector_stocks(args.sector)
        for sym in sector_syms:
            sector_stock_map[sym] = 1
        print(f"  Sector filter: {args.sector} ({len(sector_syms)} stocks)")
    else:
        top4_sectors = ranked_sectors[:4] if ranked_sectors else []
        for s in top4_sectors:
            for sym in get_sector_stocks(s["sector"]):
                if sym not in sector_stock_map:
                    sector_stock_map[sym] = s["rank"]

    for sym in backbone:
        if sym not in sector_stock_map:
            sector_stock_map[sym] = 99  # backbone stocks get neutral rank

    all_symbols = list(sector_stock_map.keys())
    print(f"  Total symbols to scan: {len(all_symbols)}")

    # ── Step 3: Fetch upcoming results ──
    print("\n[3/4] Fetching upcoming result dates...")
    try:
        upcoming = fetch_upcoming_results(days_ahead=PRE_RESULT_WINDOW)
        upcoming_map = {u["symbol"]: u["result_date"] for u in upcoming}
        print(f"  {len(upcoming)} results expected in next {PRE_RESULT_WINDOW} days")
    except Exception as e:
        print(f"  Could not fetch upcoming results: {e}")
        upcoming_map = {}

    # ── Step 4: Fetch all price data in parallel ──
    print("\n[4/4] Fetching price data and scanning stocks...")
    price_data = fetch_all_parallel(all_symbols, days=800, max_workers=10)

    results = []
    for sym in all_symbols:
        print(f"  {sym}...", end=" ", flush=True)
        try:
            df = price_data.get(sym)
            sector_rank = sector_stock_map.get(sym, 99)
            res = _analyse_stock(sym, df, sector_rank, upcoming_map)
            if res and res["score"] >= args.min_score:
                results.append(res)
                mode_tag = f"[{res['mode'].upper()}]"
                print(f"  {mode_tag} score={res['score']} | "
                      f"entry={res['entry']} | rr={res['rr']} | "
                      f"proj_growth={res['proj_yoy_growth']}%")
            else:
                print("skip")
        except Exception as e:
            print(f"err: {e}")

    if not results:
        print("\nNo setups found. Try lowering --min-score or running after more result announcements.")
        return

    df_out = pd.DataFrame(results).sort_values("score", ascending=False).head(args.top)
    out_path = os.path.join(RESULTS_DIR, f"scanner_{date.today()}.csv")
    df_out.to_csv(out_path, index=False)

    # ── Print results ──
    print(f"\n{'=' * 65}")
    print(f"  TOP {len(df_out)} EARNINGS MOMENTUM SETUPS — {date.today()}")
    print(f"{'=' * 65}")
    print(f"  {'Symbol':<18} {'Mode':<6} {'Score':>5} {'Entry':>8} {'Stop':>8} "
          f"{'Target':>8} {'RR':>5} {'Proj YoY%':>10} {'Conf':<6}")
    print("  " + "-" * 75)
    for _, row in df_out.iterrows():
        print(
            f"  {row['symbol']:<18} {row['mode'].upper():<6} {row['score']:>5} "
            f"{str(row['entry'] or '-'):>8} {str(row['stop'] or '-'):>8} "
            f"{str(row['target'] or '-'):>8} {str(row['rr'] or '-'):>5} "
            f"{str(row['proj_yoy_growth'] or '-'):>10} {str(row['proj_confidence'] or '-'):<6}"
        )

    print(f"\n  Saved to: {out_path}")
    print(f"{'=' * 65}\n")


if __name__ == "__main__":
    main()
