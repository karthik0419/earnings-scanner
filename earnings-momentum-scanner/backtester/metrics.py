"""
Backtest performance metrics.
"""

import numpy as np


def calculate_metrics(trades):
    """
    Args:
        trades: list of dicts with at least 'return_pct' and 'exit_reason'

    Returns dict with all metrics.
    """
    if not trades:
        return {
            "total_trades": 0, "win_rate": 0, "avg_return": 0,
            "avg_winner": 0, "avg_loser": 0, "profit_factor": 0,
            "max_drawdown": 0, "sharpe": 0,
        }

    returns = [t["return_pct"] for t in trades if t.get("return_pct") is not None]
    if not returns:
        return {"total_trades": len(trades), "win_rate": 0, "avg_return": 0,
                "avg_winner": 0, "avg_loser": 0, "profit_factor": 0,
                "max_drawdown": 0, "sharpe": 0}

    winners = [r for r in returns if r > 0]
    losers  = [r for r in returns if r <= 0]

    win_rate     = round(len(winners) / len(returns) * 100, 1)
    avg_return   = round(np.mean(returns), 2)
    avg_winner   = round(np.mean(winners), 2) if winners else 0
    avg_loser    = round(np.mean(losers), 2) if losers else 0
    gross_profit = sum(winners)
    gross_loss   = abs(sum(losers))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else float("inf")

    # Max drawdown — worst peak-to-trough in cumulative returns
    cum = np.cumsum(returns)
    peak = cum[0]
    max_dd = 0.0
    for val in cum:
        if val > peak:
            peak = val
        dd = peak - val
        if dd > max_dd:
            max_dd = dd
    max_dd = round(max_dd, 2)

    # Sharpe-like ratio
    std = float(np.std(returns)) if len(returns) > 1 else 0
    sharpe = round(avg_return / std, 2) if std > 0 else 0

    return {
        "total_trades":  len(returns),
        "win_rate":      win_rate,
        "avg_return":    avg_return,
        "avg_winner":    avg_winner,
        "avg_loser":     avg_loser,
        "profit_factor": profit_factor,
        "max_drawdown":  max_dd,
        "sharpe":        sharpe,
    }
