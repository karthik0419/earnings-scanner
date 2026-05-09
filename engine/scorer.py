"""
Scores each stock on earnings quality, price reaction history,
entry quality, sector momentum, and profit growth.
Max score: 100 pts.
"""


def score_stock(earnings_result, reaction_history, entry, sector_rank):
    """
    Args:
        earnings_result: dict from earnings_filter.filter_earnings()
        reaction_history: list of reaction dicts from price_reactor.measure_reaction()
        entry: dict from entry_detector.detect_entry() — may be None
        sector_rank: int rank of the stock's sector (1 = best). Use 99 if unknown.

    Returns dict with score breakdown and total.
    """
    score = 0
    breakdown = {}

    # ── 1. Earnings quality (30 pts) ──
    consistency = earnings_result.get("consistency_score", 0)
    eq_pts = min(consistency * 0.30, 30)
    score += eq_pts
    breakdown["earnings_quality"] = round(eq_pts, 1)

    # ── 2. Historical price reaction (25 pts) ──
    positive_spikes = [
        r["spike_pct"] for r in reaction_history
        if r and r.get("spike_pct", 0) > 0
    ]
    avg_spike = sum(positive_spikes) / len(positive_spikes) if positive_spikes else 0

    if avg_spike >= 5:
        rx_pts = 25
    elif avg_spike >= 3:
        rx_pts = 15
    elif avg_spike >= 1:
        rx_pts = 8
    else:
        rx_pts = 0
    score += rx_pts
    breakdown["historical_reaction"] = rx_pts

    # Bonus: sustained move after earnings (D+20 > D0)
    sustained_positive = sum(
        1 for r in reaction_history
        if r and r.get("sustained_pct") is not None and r["sustained_pct"] > 2
    )
    if sustained_positive >= 2:
        score += 5
        breakdown["sustained_bonus"] = 5
    else:
        breakdown["sustained_bonus"] = 0

    # ── 3. Entry quality (20 pts) ──
    if entry:
        rr = entry.get("rr", 0)
        if rr >= 2.5:
            eq2_pts = 20
        elif rr >= 1.5:
            eq2_pts = 12
        else:
            eq2_pts = 0
        score += eq2_pts
        breakdown["entry_quality"] = eq2_pts
    else:
        breakdown["entry_quality"] = 0

    # ── 4. Sector momentum (15 pts) ──
    if sector_rank <= 3:
        sec_pts = 15
    elif sector_rank <= 6:
        sec_pts = 8
    elif sector_rank <= 9:
        sec_pts = 4
    else:
        sec_pts = 0
    score += sec_pts
    breakdown["sector_momentum"] = sec_pts

    # ── 5. Profit growth projection (10 pts) ──
    yoy = earnings_result.get("avg_yoy_growth", 0) or 0
    if yoy > 20:
        pg_pts = 10
    elif yoy > 10:
        pg_pts = 6
    elif yoy > 0:
        pg_pts = 3
    else:
        pg_pts = 0
    score += pg_pts
    breakdown["profit_growth"] = pg_pts

    breakdown["total"] = round(score, 1)
    return breakdown
