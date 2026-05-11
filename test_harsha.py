"""
Single-stock deep analysis ? Harsha Engineers International (HARSHAENGG)
Tests: price data, earnings quality, result dates, reactions, entry, backtest
"""
import sys, os, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from datetime import date
from data.fetcher import fetch_cached
from data.earnings import fetch_earnings
from engine.earnings_filter import filter_earnings
from engine.price_reactor import measure_reaction, avg_spike
from engine.entry_detector import detect_entry
from engine.profit_estimator import estimate_current_quarter
from engine.scorer import score_stock
from data.result_dates import get_result_date
from backtester.engine import backtest_stock

# Try both possible tickers
for sym in ["HARSHAENGG.NS", "HARSHA.NS", "HARSHAENGR.NS"]:
    print(f"Trying ticker: {sym}")
    df = fetch_cached(sym, days=800)
    if df is not None and not df.empty:
        print(f"  Found! {len(df)} bars | Last close: {df['Close'].iloc[-1]:.2f}")
        print(f"  Range: {df.index[0].date()} to {df.index[-1].date()}")
        break
    else:
        print(f"  Not found")
        df = None
        sym = None

if df is None:
    print("\nNo price data found for any Harsha Engineering ticker.")
    sys.exit(0)

SEP = "=" * 65

print(f"\n{SEP}")
print(f"  HARSHA ENGINEERS INTERNATIONAL ? {sym}")
print(SEP)

# ?? Earnings ??
print("\n[1] QUARTERLY EARNINGS (screener.in)")
quarters = fetch_earnings(sym)
if not quarters:
    print("  No earnings data found")
    sys.exit(0)

print(f"  {'Quarter':<12} {'Sales':>10} {'Net Profit':>12} {'EPS':>8} {'YoY':>8}")
print("  " + "-" * 55)
for i, q in enumerate(quarters[-8:]):
    yoy = ""
    if i >= 4:
        prev = quarters[i - 4]
        if prev.get("net_profit") and q.get("net_profit"):
            g = (q["net_profit"] - prev["net_profit"]) / abs(prev["net_profit"]) * 100
            yoy = f"{g:+.1f}%"
    print(f"  {str(q.get('quarter','?')):<12} "
          f"{str(q.get('sales','?')):>10} "
          f"{str(q.get('net_profit','?')):>12} "
          f"{str(q.get('eps','?')):>8} "
          f"{yoy:>8}")

# ?? Earnings filter ??
print(f"\n[2] EARNINGS QUALITY CHECK")
ef = filter_earnings(quarters)
print(f"  Passes filter : {ef['passes']}")
print(f"  Reason        : {ef.get('reason','OK')}")
print(f"  Consistency   : {ef['consistency_score']}/100")
print(f"  Avg YoY growth: {ef.get('avg_yoy_growth','N/A')}%")
print(f"  Growth quarters: {ef.get('growth_quarters','N/A')}/4")

# ?? Result dates & reactions ??
print(f"\n[3] RESULT DATES & PRICE REACTIONS (last 4 quarters)")
valid_qs  = [q for q in quarters if q.get("quarter")]
last4     = valid_qs[-4:]
reactions = []
print(f"  {'Quarter':<12} {'Result Date':<14} {'D-1':>8} {'D0':>8} {'Spike%':>8} {'D+5':>8} {'D+20':>8} {'Type':<10}")
print("  " + "-" * 75)
for q in last4:
    rd = get_result_date(sym, q["quarter"], price_df=df)
    if rd is None:
        print(f"  {q['quarter']:<12} {'No date found':<14}")
        continue
    rx = measure_reaction(sym, rd, df)
    if rx:
        reactions.append(rx)
        print(f"  {q['quarter']:<12} {str(rd):<14} "
              f"{str(rx.get('d_minus1','?')):>8} "
              f"{str(rx.get('d0','?')):>8} "
              f"{str(rx.get('spike_pct','?')):>8} "
              f"{str(rx.get('d5','?')):>8} "
              f"{str(rx.get('d20','?')):>8} "
              f"{rx.get('spike_type','?'):<10}")
    else:
        print(f"  {q['quarter']:<12} {str(rd):<14} {'no reaction data'}")

avg = avg_spike(reactions)
print(f"\n  Avg spike across last 4 results: {avg}%")

# ?? Current result window ??
print(f"\n[4] CURRENT SETUP STATUS")
last_q = valid_qs[-1]["quarter"] if valid_qs else None
result_date = get_result_date(sym, last_q, price_df=df) if last_q else None
today = date.today()

if result_date:
    delta = (today - result_date).days
    if 0 <= delta <= 45:
        print(f"  POST-RESULT: {delta} days since {result_date}")
        mode = "post"
    elif -30 <= delta < 0:
        print(f"  PRE-RESULT:  {abs(delta)} days until {result_date}")
        mode = "pre"
    else:
        print(f"  OUT OF WINDOW: result was {delta} days ago ({result_date})")
        mode = None
else:
    print("  Could not determine result date")
    mode = None

# ?? Entry detection ??
print(f"\n[5] ENTRY SETUP")
entry_info = None
if mode == "post" and reactions:
    last_rx = reactions[-1]
    spike = last_rx.get("spike_pct", 0)
    if spike >= 2:
        entry_info = detect_entry(df, result_date, last_rx.get("d0"))
        if entry_info:
            cmp = float(df["Close"].iloc[-1])
            print(f"  CMP          : {cmp:.2f}")
            print(f"  Entry        : {entry_info['entry']:.2f}")
            print(f"  Stop         : {entry_info['stop']:.2f}  ({((entry_info['stop']-entry_info['entry'])/entry_info['entry']*100):.1f}%)")
            print(f"  Target       : {entry_info['target']:.2f}  ({((entry_info['target']-entry_info['entry'])/entry_info['entry']*100):.1f}%)")
            print(f"  Risk:Reward  : {entry_info['rr']:.2f}x")
            print(f"  Pullback days: {entry_info['pullback_days']}")
            if cmp <= entry_info['entry'] * 1.02:
                print(f"  >>> PRICE IS NEAR ENTRY ? actionable now!")
            else:
                print(f"  >>> Price ({cmp:.2f}) is above entry ({entry_info['entry']:.2f}) ? wait for pullback")
        else:
            print("  No valid entry setup (RR < 1.5 or no pullback)")
    else:
        print(f"  Spike was only {spike:.1f}% ? below 2% threshold, no trade")
else:
    print("  Entry detection only runs in POST-result window")

# ?? Profit projection ??
print(f"\n[6] NEXT QUARTER PROFIT PROJECTION")
proj = estimate_current_quarter(quarters)
print(f"  Projected Net Profit: {proj['projected_net_profit']}")
print(f"  Projected EPS       : {proj['projected_eps']}")
print(f"  YoY growth est.     : {proj['yoy_growth_pct']}%")
print(f"  Confidence          : {proj['confidence']}")

# ?? Scoring ??
print(f"\n[7] SCORE BREAKDOWN")
score = score_stock(ef, reactions, entry_info, sector_rank=5)
print(f"  Earnings quality  : {score.get('earnings_quality',0)}/30")
print(f"  Reaction history  : {score.get('reaction_history',0)}/30")
print(f"  Entry quality     : {score.get('entry_quality',0)}/20")
print(f"  Sector momentum   : {score.get('sector_momentum',0)}/15")
print(f"  Profit growth     : {score.get('profit_growth',0)}/10")
print(f"  ---------------------")
print(f"  TOTAL SCORE       : {score['total']}/100")

# ?? Backtest ??
print(f"\n[8] HISTORICAL BACKTEST (last 4 quarters)")
bt = backtest_stock(sym, quarters, df)
trades = bt["trades"]
if trades:
    m = bt["metrics"]
    print(f"  {'Quarter':<12} {'Spike%':>7} {'Entry':>8} {'Exit':>8} {'Return%':>9} {'Exit Reason':<14} {'Days':>5} {'Result'}")
    print("  " + "-" * 75)
    for t in trades:
        print(f"  {t['quarter']:<12} {t['spike_pct']:>7.1f} {t['entry_price']:>8.2f} "
              f"{t['exit_price']:>8.2f} {t['return_pct']:>9.2f}%  "
              f"{t['exit_reason']:<14} {t['days_held']:>5}   {t['result']}")
    print(f"\n  Trades      : {m['total_trades']}")
    print(f"  Win Rate    : {m['win_rate']}%")
    print(f"  Avg Return  : {m['avg_return']}%")
    print(f"  Avg Winner  : {m['avg_winner']}%")
    print(f"  Avg Loser   : {m['avg_loser']}%")
    print(f"  Profit Factor: {m['profit_factor']}")
else:
    print("  No trades generated ? no qualifying spikes or pullback entries found")

print(f"\n{SEP}")
print(f"  FINAL VERDICT")
print(SEP)
total = score['total']
has_entry = entry_info and entry_info.get('rr', 0) >= 2.0
if total >= 75 and has_entry:
    print(f"  STRONG BUY ? Score {total}/100, RR {entry_info['rr']:.1f}x. Enter now.")
elif total >= 60 and has_entry:
    print(f"  BUY ? Score {total}/100, RR {entry_info['rr']:.1f}x. Good setup.")
elif total >= 60:
    print(f"  WATCHLIST ? Score {total}/100. Earnings strong, wait for entry trigger.")
elif total >= 40:
    print(f"  WEAK ? Score {total}/100. Mixed signals. Monitor only.")
else:
    print(f"  SKIP ? Score {total}/100. Doesn't meet criteria.")
print(SEP)
