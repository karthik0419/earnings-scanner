"""
Backtest report — prints summary and saves CSV.
"""

import os
import pandas as pd
from datetime import date

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
os.makedirs(RESULTS_DIR, exist_ok=True)


def generate_report(results_df, metrics, filename=None):
    """
    Print formatted backtest report and save CSV.

    Args:
        results_df: DataFrame with all trade records
        metrics: dict from calculate_metrics()
        filename: optional override for output filename
    """
    if filename is None:
        filename = os.path.join(RESULTS_DIR, f"backtest_{date.today()}.csv")

    sep = "=" * 75

    print(f"\n{sep}")
    print("  EARNINGS MOMENTUM BACKTEST — RESULTS")
    print(sep)
    print(f"  Total Trades  : {metrics['total_trades']}")
    print(f"  Win Rate      : {metrics['win_rate']}%")
    print(f"  Avg Return    : {metrics['avg_return']}%")
    print(f"  Avg Winner    : {metrics['avg_winner']}%")
    print(f"  Avg Loser     : {metrics['avg_loser']}%")
    print(f"  Profit Factor : {metrics['profit_factor']}")
    print(f"  Max Drawdown  : -{metrics['max_drawdown']}%")
    print(f"  Sharpe Ratio  : {metrics['sharpe']}")
    print(sep)

    if not results_df.empty:
        # Per-stock summary
        per_stock = (
            results_df.groupby("symbol")
            .agg(
                trades=("return_pct", "count"),
                win_rate=("return_pct", lambda x: round((x > 0).mean() * 100, 1)),
                avg_return=("return_pct", lambda x: round(x.mean(), 2)),
                total_return=("return_pct", lambda x: round(x.sum(), 2)),
            )
            .sort_values("avg_return", ascending=False)
            .reset_index()
        )

        print("\n  PER-STOCK SUMMARY (top performers):")
        print(f"  {'Symbol':<20} {'Trades':>6} {'Win%':>6} {'Avg Ret%':>9} {'Total%':>9}")
        print("  " + "-" * 55)
        for _, row in per_stock.head(20).iterrows():
            print(f"  {row['symbol']:<20} {int(row['trades']):>6} {row['win_rate']:>6} {row['avg_return']:>9} {row['total_return']:>9}")

        # Fast per-stock summary CSV
        summary_path = filename.replace(".csv", "_summary.csv")
        try:
            per_stock.to_csv(summary_path, index=False)
            print(f"\n  Summary saved to  : {summary_path}")
        except Exception:
            pass

        print(f"  Full trades saved to: {filename}")
        try:
            results_df.to_csv(filename, index=False)
        except Exception as e:
            print(f"  Warning: could not save CSV — {e}")

    print(sep)
