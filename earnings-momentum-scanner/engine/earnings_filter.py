"""
Earnings consistency filter.
Requires 4+ quarters of data with consistent profit growth.
"""


def filter_earnings(quarters):
    """
    Filter stocks by earnings quality.

    Returns dict with:
      passes: bool
      growth_quarters: int
      avg_yoy_growth: float
      consistency_score: float (0-100)
    """
    result = {
        "passes": False,
        "growth_quarters": 0,
        "avg_yoy_growth": 0.0,
        "consistency_score": 0.0,
    }

    if not quarters or len(quarters) < 4:
        return result

    # Use last 8 quarters max
    qs = [q for q in quarters if q.get("net_profit") is not None]
    if len(qs) < 4:
        return result

    last4 = qs[-4:]

    # Criterion 1: Net profit positive in last 3 quarters
    positives = sum(1 for q in last4[-3:] if (q["net_profit"] or 0) > 0)
    if positives < 3:
        return result

    # Criterion 2: YoY growth — need same quarter from a year ago
    yoy_growths = []
    for i in range(len(qs) - 4, len(qs)):
        current_q = qs[i]
        # Same quarter last year = 4 quarters back
        prior_idx = i - 4
        if prior_idx < 0:
            continue
        prior_q = qs[prior_idx]
        cp = current_q.get("net_profit")
        pp = prior_q.get("net_profit")
        if cp is None or pp is None or pp == 0:
            continue
        growth = (cp - pp) / abs(pp) * 100
        yoy_growths.append(growth)

    growth_quarters = sum(1 for g in yoy_growths if g > 0)
    avg_yoy = sum(yoy_growths) / len(yoy_growths) if yoy_growths else 0

    # Criterion 3: No single quarter with >30% QoQ decline
    for i in range(1, len(last4)):
        prev = last4[i - 1].get("net_profit") or 0
        curr = last4[i].get("net_profit") or 0
        if prev > 0 and curr < prev * 0.70:
            return result

    if len(yoy_growths) >= 3 and growth_quarters < 3:
        return result

    # Consistency score (0-100)
    score = 0.0
    # Positive profit streak
    score += min(positives / 3 * 30, 30)
    # YoY growth quality
    if avg_yoy > 30:
        score += 40
    elif avg_yoy > 20:
        score += 30
    elif avg_yoy > 10:
        score += 20
    elif avg_yoy > 0:
        score += 10
    # Growth quarter consistency
    score += min(growth_quarters / max(len(yoy_growths), 1) * 30, 30)

    result["passes"] = True
    result["growth_quarters"] = growth_quarters
    result["avg_yoy_growth"] = round(avg_yoy, 2)
    result["consistency_score"] = round(score, 1)
    return result
