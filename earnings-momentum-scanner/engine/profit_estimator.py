"""
Projects current quarter net profit and EPS from last 4-8 quarters.
Uses 60% YoY + 40% QoQ linear trend.
"""

import numpy as np


def _coeff_of_variation(values):
    """Measure volatility of a series — lower = more consistent."""
    values = [v for v in values if v is not None]
    if len(values) < 2:
        return 1.0
    mean = np.mean(values)
    if mean == 0:
        return 1.0
    return float(np.std(values) / abs(mean))


def estimate_current_quarter(quarters):
    """
    Project current quarter net profit and EPS from historical quarters.

    Args:
        quarters: list of dicts with 'net_profit', 'eps', 'sales' — oldest first

    Returns dict with projection details.
    """
    valid = [q for q in quarters if q.get("net_profit") is not None]

    if len(valid) < 4:
        return {
            "projected_net_profit": None,
            "projected_eps":        None,
            "yoy_growth_pct":       None,
            "confidence":           "low",
        }

    profits = [q["net_profit"] for q in valid]
    eps_vals = [q.get("eps") for q in valid]

    # ── YoY growth component ──
    # Compare last quarter to same quarter one year ago (4 quarters back)
    yoy_growths = []
    for i in range(4, len(profits)):
        curr = profits[i]
        prev = profits[i - 4]
        if prev and prev != 0:
            yoy_growths.append((curr - prev) / abs(prev))

    avg_yoy_rate = float(np.mean(yoy_growths)) if yoy_growths else 0.0
    last_profit = profits[-1]
    last_profit_yoy_base = profits[-5] if len(profits) >= 5 else profits[-1]

    yoy_projection = last_profit_yoy_base * (1 + avg_yoy_rate) if last_profit_yoy_base else last_profit

    # ── QoQ trend component (linear regression on last 4 quarters) ──
    last4_profits = profits[-4:]
    xs = np.arange(len(last4_profits))
    try:
        slope, intercept = np.polyfit(xs, last4_profits, 1)
        qoq_projection = intercept + slope * len(last4_profits)
    except Exception:
        qoq_projection = last_profit

    # ── Weighted average ──
    projected_profit = 0.6 * yoy_projection + 0.4 * qoq_projection

    # ── EPS projection ──
    valid_eps = [e for e in eps_vals if e is not None]
    projected_eps = None
    if valid_eps and valid[-1].get("net_profit") and valid[-1]["net_profit"] != 0:
        eps_ratio = valid_eps[-1] / valid[-1]["net_profit"]
        projected_eps = round(projected_profit * eps_ratio, 2)

    # ── Confidence ──
    cv = _coeff_of_variation(profits[-4:])
    if cv < 0.20:
        confidence = "high"
    elif cv < 0.45:
        confidence = "medium"
    else:
        confidence = "low"

    yoy_growth_pct = round(avg_yoy_rate * 100, 2) if yoy_growths else None

    return {
        "projected_net_profit": round(projected_profit, 2),
        "projected_eps":        projected_eps,
        "yoy_growth_pct":       yoy_growth_pct,
        "confidence":           confidence,
    }
