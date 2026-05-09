"""
Screener.in quarterly financials scraper.
Fetches Sales, Net Profit, EPS for last 8 quarters per stock.
Cached to disk for 12 hours.
"""

import os
import json
import time
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.screener.in/",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def _cache_path(symbol):
    safe = symbol.replace(".", "_").replace("/", "_")
    return os.path.join(CACHE_DIR, f"{safe}_earnings.json")


def _is_fresh(path, max_age_hours=12):
    if not os.path.exists(path):
        return False
    age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(path))
    return age < timedelta(hours=max_age_hours)


def _parse_number(text):
    if not text:
        return None
    text = text.strip().replace(",", "").replace("%", "")
    if text in ("-", "", "--", "N/A"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _scrape_screener(symbol):
    """Try consolidated first, fallback to standalone."""
    bare = symbol.replace(".NS", "").replace(".BO", "").upper()
    urls = [
        f"https://www.screener.in/company/{bare}/consolidated/",
        f"https://www.screener.in/company/{bare}/",
    ]

    for url in urls:
        try:
            resp = SESSION.get(url, timeout=15)
            if resp.status_code == 200 and "Quarterly Results" in resp.text:
                return resp.text
        except Exception:
            continue
        time.sleep(0.5)

    return None


def _parse_quarters(html):
    soup = BeautifulSoup(html, "html.parser")

    # Find the Quarterly Results section
    quarterly_section = None
    for section in soup.find_all("section"):
        h2 = section.find("h2")
        if h2 and "Quarterly Results" in h2.get_text():
            quarterly_section = section
            break

    if not quarterly_section:
        # Try finding table with quarterly data directly
        for table in soup.find_all("table", class_=re.compile("data-table")):
            th_texts = [th.get_text(strip=True) for th in table.find_all("th")]
            if any(re.search(r"(Mar|Jun|Sep|Dec)\s+\d{4}", t) for t in th_texts):
                quarterly_section = table.parent
                break

    if not quarterly_section:
        return []

    table = quarterly_section.find("table")
    if not table:
        return []

    rows = table.find_all("tr")
    if not rows:
        return []

    # Extract column headers (quarter labels)
    header_row = rows[0]
    headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]
    # First header is usually the row label, rest are quarter dates
    quarter_labels = headers[1:]

    quarters_data = {q: {} for q in quarter_labels}

    row_map = {
        "Sales": "sales",
        "Net Profit": "net_profit",
        "EPS in Rs": "eps",
        "EPS": "eps",
        "Earnings Per Share": "eps",
    }

    for row in rows[1:]:
        cells = row.find_all(["th", "td"])
        if not cells:
            continue
        row_label = cells[0].get_text(strip=True)

        matched_key = None
        for label, key in row_map.items():
            if label.lower() in row_label.lower():
                matched_key = key
                break

        if not matched_key:
            continue

        for i, cell in enumerate(cells[1:]):
            if i >= len(quarter_labels):
                break
            val = _parse_number(cell.get_text(strip=True))
            quarters_data[quarter_labels[i]][matched_key] = val

    result = []
    for q_label in quarter_labels:
        data = quarters_data[q_label]
        if not data:
            continue
        result.append({
            "quarter": q_label,
            "sales": data.get("sales"),
            "net_profit": data.get("net_profit"),
            "eps": data.get("eps"),
        })

    # Sort oldest first
    def _quarter_sort_key(item):
        label = item["quarter"]
        month_map = {"Mar": 3, "Jun": 6, "Sep": 9, "Dec": 12}
        m = re.search(r"(Mar|Jun|Sep|Dec)\s+(\d{4})", label)
        if m:
            return int(m.group(2)) * 100 + month_map.get(m.group(1), 0)
        return 0

    result.sort(key=_quarter_sort_key)
    return result


def fetch_earnings(symbol):
    """
    Fetch quarterly financials for a stock from screener.in.
    Returns list of dicts sorted oldest first.
    """
    path = _cache_path(symbol)

    if _is_fresh(path):
        try:
            with open(path, "r") as f:
                cached = json.load(f)
            if cached:
                return cached
        except Exception:
            pass

    time.sleep(1)  # rate limit
    html = _scrape_screener(symbol)
    if not html:
        return []

    quarters = _parse_quarters(html)

    if quarters:
        try:
            with open(path, "w") as f:
                json.dump(quarters, f)
        except Exception:
            pass

    return quarters
