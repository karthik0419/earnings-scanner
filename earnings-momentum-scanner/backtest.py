"""
Standalone backtest runner for earnings momentum strategy.

Usage:
  python backtest.py --stocks nifty500.txt --top 100
  python backtest.py --symbols RELIANCE TCS INFY
  python backtest.py --stocks backbone50.txt
"""

import sys
import os
import argparse
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtester.engine import run_backtest
from backtester.metrics import calculate_metrics
from backtester.report import generate_report


def _load_list(path):
    try:
        with open(path) as f:
            return [l.strip() for l in f if l.strip() and not l.startswith("#")]
    except FileNotFoundError:
        print(f"File not found: {path}")
        return []


def main():
    parser = argparse.ArgumentParser(description="Earnings Momentum Backtester")
    parser.add_argument("--stocks",  type=str, default=None,
                        help="Path to stock list file e.g. nifty500.txt")
    parser.add_argument("--symbols", nargs="+", default=None,
                        help="Direct symbol list e.g. --symbols RELIANCE TCS")
    parser.add_argument("--top",     type=int, default=50,
                        help="Max number of stocks to backtest")
    args = parser.parse_args()

    if args.symbols:
        symbols = args.symbols
    elif args.stocks:
        symbols = _load_list(args.stocks)
    else:
        symbols = _load_list("backbone50.txt")

    if not symbols:
        print("No symbols provided.")
        sys.exit(1)

    symbols = symbols[: args.top]

    print("=" * 65)
    print("  EARNINGS MOMENTUM BACKTEST")
    print(f"  Stocks: {len(symbols)}")
    print("=" * 65)
    print()

    results_df = run_backtest(symbols)

    if results_df.empty:
        print("\nNo trades generated. Check earnings data availability.")
        return

    trades = results_df.to_dict("records")
    metrics = calculate_metrics(trades)

    generate_report(results_df, metrics)

    print(f"\n  SUMMARY: {metrics['total_trades']} trades | "
          f"Win Rate: {metrics['win_rate']}% | "
          f"Avg Return: {metrics['avg_return']}%\n")


if __name__ == "__main__":
    main()
