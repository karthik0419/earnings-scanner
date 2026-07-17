# Earnings Momentum Scanner (swing-scanner-v3)

Scans NSE stocks for post-earnings momentum setups. Finds stocks that spike after quarterly results, detects pullback entry points, scores them, and builds a monthly watchlist.

Strategy: **Post-Earnings Announcement Drift (PEAD)** — stocks that gap up strongly on results tend to continue higher after a brief pullback. Enter the pullback, ride the continuation.

---

## Quick Start

Double-click `run_weekly.bat` and pick a mode:

```
1. Weekly Scan     — 588 stocks, all NSE sectors       (~30 min, every Saturday)
2. Discovery Scan  — 2131 stocks, full NSE EQ list     (~90 min, once a month)
3. Daily Scan      — Top sector stocks + backbone       (~10 min, weekdays)
```

Results saved to `results/scanner_YYYY-MM-DD.csv` and `results/watchlist_YYYY-MM.csv`

---

## Installation

```bash
git clone https://github.com/karthik0419/earnings-momentum-scanner
cd earnings-momentum-scanner
pip install -r requirements.txt
```

**requirements.txt**
```
pandas
numpy
requests
yfinance
jugaad-data
mplfinance
beautifulsoup4
```

---

## How to Run

### Option 1 — BAT file (recommended)
```
Double-click run_weekly.bat → select 1, 2, or 3
```

### Option 2 — Command line
```bash
# Weekly scan (every Saturday)
python scanner.py --mode weekly --top 30 --min-score 35 --delay 2.0

# Discovery scan (monthly — catches below-index stocks like recent IPOs)
python scanner.py --mode discovery --top 50 --min-score 40 --delay 2.5

# Daily quick scan
python scanner.py --mode daily --top 20 --min-score 40

# Single sector scan
python scanner.py --mode weekly --sector IT

# Backtest on specific stocks
python backtest.py --symbols TCS INFY HCLTECH WIPRO --top 20
python backtest.py --stocks backbone50.txt
```

---

## Scan Modes

| Mode | Universe | Stocks | ETA | When to run |
|------|----------|--------|-----|-------------|
| weekly | All NSE sector indices + hardcoded sectors | 588 | 25-35 min | Every Saturday |
| discovery | Full NSE EQ-series list | 2,131 | ~90 min | First Saturday of month |
| daily | Top 4 sectors by momentum + backbone | ~100 | 5-10 min | Weekdays (optional) |

---

## Stock Universe

### Weekly scan — 588 stocks from:

**NSE Index Constituents (fetched live from niftyindices.com)**
| Index | Stocks |
|-------|--------|
| Nifty 50 | 50 |
| Nifty Next 50 | 50 |
| Nifty 500 | 504 (top 500 by market cap) |
| Nifty Largemidcap 250 | 254 |
| Nifty Midcap 150 | 150 |
| Nifty Smallcap 250 | 250 |
| Nifty Midcap 50 | 50 |
| IT, Bank, Pharma, Auto, FMCG, Metal, Realty, Energy, Media | sector-wise |
| PSU Bank, Financial Services, Healthcare, Consumption, Infra, PSE, MNC, Oil & Gas, Commodities | thematic |

**Hardcoded sectors (niftyindices.com CSV not available)**
| Sector | Stocks | Key names |
|--------|--------|-----------|
| Defense | 14 | HAL, BEL, GRSE, MAZDOCK, MTARTECH, DCX |
| Chemicals | 24 | PIDILITIND, VINATIORGA, NAVINFLUOR, SRF, DEEPAKNTR |
| Capital Markets | 17 | MCX, CDSL, BSE, ANGELONE, KFINTECH, CAMS, MOTILALOFS |
| EV & New Age Auto | 15 | OLECTRA, KAYNES, SONACOMS, AMARAJABAT, TATAELXSI |
| New Age Tech | 17 | ZOMATO, NYKAA, LATENTVIEW, MAPMYINDIA, RATEGAIN |
| Textiles | 14 | PAGEIND, WELSPUNLIV, RAYMOND, TRIDENT, FILATEX |
| Agri & Fertilizers | 13 | COROMANDEL, PIIND, CHAMBLFERT, DHANUKA, BAYERCROP |
| Logistics | 10 | DELHIVERY, CONCOR, BLUEDART, MAHLOG, VRLLOG |
| Power | 13 | TATAPOWER, JSWENERGY, INOXWIND, SUZLON, NHPC |
| Telecom | 11 | BHARTIARTL, HFCL, STLTECH, RAILTEL, TEJASNET |
| Quality Small Caps | 28 | HARSHA, SYRMA, AVALON, GRAVITA, BIKAJI, SBFC |

**Deduplication:** Broad indices are fetched first — a stock in both Nifty 50 and IT index keeps the "Nifty 50" tag. Sector tags are only assigned to stocks not already in broader indices.

### Discovery scan — 2,131 stocks
Fetches NSE's full EQ-series equity master list. Finds 1,559 stocks not in any NSE index — recent IPOs, micro-caps, newly listed quality companies. Cache: 7 days.

---

## How the Strategy Works

```
For each stock:
  1. Fetch quarterly earnings from screener.in
  2. Check earnings quality filter (4+ quarters, profitable, YoY growth)
  3. Detect result date (NSE calendar OR price-spike auto-detection)
  4. Measure price reaction on result day (D-1 vs D0 close)
  5. If spike >= 2%: look for pullback entry (D+1 to D+10)
  6. Entry = pullback low, Stop = entry * 0.97, Target = spike_close + move * 1.5
  7. Score the setup (earnings quality + reaction history + entry quality + sector momentum + profit growth)
  8. Flag as ENTER NOW if post-result + RR >= 2.0
```

### Earnings Filter
- Minimum 4 quarters of data
- Net profit positive in last 3 quarters
- YoY growth in at least 3 of last 4 quarters
- No more than 30% QoQ decline

### Entry Detection
- Looks at D+1 to D+15 after result
- Entry = lowest close in D+1 to D+10 (pullback low)
- Stop = pullback_low * 0.97 (3% below entry)
- Target = spike_close + (spike_move * 1.5)
- Skips if RR < 1.5

### Scoring (100 pts max)
| Component | Max | What it checks |
|-----------|-----|----------------|
| Earnings quality | 30 | Consistency score from filter |
| Reaction history | 30 | Avg spike % over last 4 results |
| Entry quality | 20 | RR ratio of current setup |
| Sector momentum | 15 | Sector 20d + 5d return rank |
| Profit growth | 10 | YoY EPS growth projection |

---

## Output

### Scanner results (`results/scanner_YYYY-MM-DD.csv`)
| Column | Description |
|--------|-------------|
| symbol | NSE ticker (.NS) |
| sector | Sector tag |
| status | ENTER NOW / WATCH |
| score | 0-100 setup score |
| cmp | Current market price |
| entry | Suggested entry price |
| stop | Stop loss |
| target | Price target |
| rr | Risk/Reward ratio |
| result_date | Detected result announcement date |
| days_since_result | Days since result (post-result window) |
| proj_yoy_growth | Projected next quarter YoY growth % |
| proj_confidence | Projection confidence (high/medium/low) |
| avg_spike_pct | Average spike % across last 4 results |

### Monthly watchlist (`results/watchlist_YYYY-MM.csv`)
Cumulative across all Saturday scans of the month. Deduped by symbol — keeps highest score if a stock appears multiple times.

---

## Project Structure

```
earnings-momentum-scanner/
|
|-- run_weekly.bat            # One-click runner with mode menu
|-- scanner.py                # Main scanner — weekly / daily / discovery
|-- backtest.py               # Standalone backtester CLI
|-- backbone50.txt            # 62 curated stocks always included in daily scan
|-- nifty500.txt              # Fallback universe
|
|-- data/
|   |-- nse_universe.py       # Universe builder — NSE indices + hardcoded sectors
|   |-- fetcher.py            # Parallel price fetch + disk cache (800 days)
|   |-- earnings.py           # Screener.in quarterly earnings scraper
|   |-- result_dates.py       # Result date detection (NSE calendar + price spike)
|   |-- sectors.py            # Sector momentum ranking
|   |-- loader.py             # jugaad-data NSE price loader
|
|-- engine/
|   |-- earnings_filter.py    # Earnings quality filter
|   |-- price_reactor.py      # Measures D-1/D0/D+5/D+20 price reactions
|   |-- entry_detector.py     # Pullback entry detection (D+1 to D+15)
|   |-- scorer.py             # 100-pt scoring engine
|   |-- profit_estimator.py   # Next quarter profit projection
|
|-- backtester/
|   |-- engine.py             # Walk-forward backtest, no lookahead bias
|   |-- metrics.py            # Win rate, profit factor, Sharpe, drawdown
|   |-- report.py             # Per-stock summary + CSV output
|
|-- results/                  # Auto-generated scan outputs
|-- cache/                    # Price data + earnings cache (gitignored)
```

---

## Backtester

```bash
# Backtest on backbone list
python backtest.py --stocks backbone50.txt

# Backtest on specific symbols
python backtest.py --symbols RELIANCE TCS INFY HDFCBANK ICICIBANK

# Top 100 from Nifty 500
python backtest.py --stocks nifty500.txt --top 100
```

**Backtest output**
```
Total Trades   : 24
Win Rate       : 54.2%
Avg Return     : +1.71%
Avg Winner     : +5.5%
Avg Loser      : -2.77%
Profit Factor  : 2.35       <- earns Rs 2.35 for every Rs 1 lost
Max Drawdown   : -9.0%
Sharpe Ratio   : 0.36
```

Results saved to `results/backtest_YYYY-MM-DD.csv`

---

## Scheduling

Suggested weekly rhythm:

| Day | Action |
|-----|--------|
| Saturday (weekly) | `run_weekly.bat` → Option 1 (588 stocks) |
| First Saturday of month | `run_weekly.bat` → Option 2 (discovery, 2131 stocks) |
| Weekdays (optional) | `run_weekly.bat` → Option 3 (daily, ~100 stocks) |
| After scan | Review ENTER NOW setups, cross-check chart on TradingView |

---

## Version History

### v1.0 — Initial build (2026-05-09)
- Earnings momentum scanner with screener.in data
- Quarterly earnings filter, result date detection, pullback entry logic
- Scoring: earnings quality + reaction history + entry + sector + profit growth
- Walk-forward backtester with no lookahead bias
- Weekly and daily scan modes
- Backbone50 curated stock list

### v2.0 — Sector-wise universe (2026-05-09)
- Switched from static list to live NSE sector index constituents
- 23 sector/thematic indices fetched from niftyindices.com
- Defense stocks hardcoded (15 stocks) — CSV not available from NSE
- 382 unique quality stocks
- DUMMY symbol filter added (niftyindices.com injects placeholder rows)

### v3.0 — Full sector coverage (2026-05-10)
- Added 10 hardcoded sectors missing from niftyindices.com:
  Chemicals, Capital Markets, EV & New Age Auto, New Age Tech, Textiles,
  Agri & Fertilizers, Logistics, Power, Telecom, Quality Small Caps
- Wrong NSE tickers fixed: MCXINDIA->MCX, MOTILALOSW->MOTILALOFS,
  AMARARAJA->AMARAJABAT, CHAMBAL->CHAMBLFERT, BAYER->BAYERCROP,
  MTAR->MTARTECH, DCXSYS->DCX, VRL->VRLLOG, and more
- Universe: 455 unique verified stocks

### v4.0 — Extended universe + Discovery mode (2026-05-10)
- Added Nifty 500, Smallcap 250, Largemidcap 250, Midcap 50 to index list
- Added Quality Small Caps hardcoded list (HARSHA, SYRMA, AVALON, GRAVITA...)
- Weekly universe: 455 -> 588 unique stocks
- New `--mode discovery`: fetches full NSE EQ-series list (2131 stocks)
  Catches recent IPOs, micro-caps, below-index stocks not in any NSE index
- `fetch_extended_universe()` function returns 1559 below-index stocks
- NSE EQ list cached for 7 days
- `run_weekly.bat` updated with 3-mode selection menu

---

## Known Limitations

- Screener.in earnings data requires ~2s per stock (rate limiting) — hence the 30 min scan time
- Result date detection is auto-detected from price spikes — occasionally off by 1-2 days
- NSE event calendar API is cookie-gated and unreliable — price-spike detection is the primary method
- Discovery mode (~90 min) has many illiquid stocks — min-score 40 filters most of them out
- Profit projection is a linear regression — unreliable when a stock had one bad quarter (outlier)

---

## Disclaimer

For educational and research purposes only. Not financial advice. Trading involves substantial risk of loss.
