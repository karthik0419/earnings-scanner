"""Quick end-to-end smoke test for the swing-scanner-v3 pipeline."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date

print("=" * 60)
print("  SWING SCANNER V3 — PIPELINE SMOKE TEST")
print("=" * 60)

# 1. Earnings fetch
print("\n[1] Earnings fetch (TCS) ...")
from data.earnings import fetch_earnings
qs = fetch_earnings("TCS")
print(f"    Quarters: {len(qs)}")
for q in qs[-3:]:
    print(f"    {q}")

# 2. Earnings filter
print("\n[2] Earnings filter ...")
from engine.earnings_filter import filter_earnings
ef = filter_earnings(qs)
print(f"    passes={ef['passes']}  growth_q={ef['growth_quarters']}  "
      f"avg_yoy={ef['avg_yoy_growth']}%  score={ef['consistency_score']}")

# 3. Profit estimator
print("\n[3] Profit estimator ...")
from engine.profit_estimator import estimate_current_quarter
proj = estimate_current_quarter(qs)
print(f"    proj_profit={proj['projected_net_profit']}  proj_eps={proj['projected_eps']}  "
      f"yoy={proj['yoy_growth_pct']}%  conf={proj['confidence']}")

# 4. Price fetch
print("\n[4] Price fetch (TCS.NS, 800d) ...")
from data.fetcher import fetch_cached
df = fetch_cached("TCS.NS", days=800)
print(f"    Rows: {len(df) if df is not None else 0}")

# 5. Price reaction on a known past result date
print("\n[5] Price reaction (TCS Q3 FY25 — 2025-01-09) ...")
from engine.price_reactor import measure_reaction
result_date = date(2025, 1, 9)
rx = measure_reaction("TCS", result_date, df)
if rx:
    print(f"    spike={rx['spike_pct']}%  class={rx['classification']}  "
          f"sustained={rx['sustained_pct']}%")
else:
    print("    No reaction data (date may be outside price history range)")

# 6. Entry detection
if rx and rx.get("spike_pct", 0) >= 2:
    print("\n[6] Entry detection ...")
    from engine.entry_detector import detect_entry
    entry = detect_entry(df, result_date, rx["d0"])
    if entry:
        print(f"    entry={entry['entry']}  stop={entry['stop']}  "
              f"target={entry['target']}  rr={entry['rr']}  "
              f"pullback_days={entry['pullback_days']}")
    else:
        print("    No valid entry (RR < 1.5 or no pullback)")
else:
    print("\n[6] Entry detection — skipped (spike < 2%)")

# 7. Scorer
print("\n[7] Scorer ...")
from engine.scorer import score_stock
reactions = [rx] if rx else []
entry_info = None
if rx and rx.get("spike_pct", 0) >= 2:
    from engine.entry_detector import detect_entry
    entry_info = detect_entry(df, result_date, rx["d0"])
breakdown = score_stock(ef, reactions, entry_info, sector_rank=2)
print(f"    Breakdown: {breakdown}")

# 8. Backtest (single stock, quick)
print("\n[8] Backtest (TCS, last 4 quarters) ...")
from backtester.engine import backtest_stock
bt = backtest_stock("TCS.NS", qs, df)
print(f"    Trades: {len(bt['trades'])}")
for t in bt["trades"]:
    print(f"    Q={t['quarter']}  spike={t['spike_pct']}%  "
          f"entry={t['entry_price']}  exit={t['exit_price']}  "
          f"ret={t['return_pct']}%  [{t['exit_reason']}]")
print(f"    Metrics: {bt['metrics']}")

print("\n" + "=" * 60)
print("  SMOKE TEST COMPLETE")
print("=" * 60)
