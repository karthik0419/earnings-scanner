# AGENTS.md — Workspace Map

Workspace root: `F:\projects\claude`
Owner: Kartik Bandewar (DevOps/SRE engineer, Pune, India)
Platform: Windows (PowerShell). Python projects use `python` (not `python3`).

This workspace holds **16 projects across 3 domains**:
1. Stock trading screeners (Python)
2. Job-hunting automation (Python + Chrome extension)
3. Restaurant POS SaaS — TableFlow (Node.js microservices)

> **Workspace layout (2026-07-18):** The root `F:\projects\claude` is a clean container — only `AGENTS.md`, `interview-prep.md`, and per-project subfolders live here. No loose project files at root. The root `.git` tracks the `earnings-momentum-scanner/` subfolder (commit `4430bda` restructured loose root files into that subfolder). All other project subfolders are untracked.

---

## Quick Navigation

| Project | Domain | Stack | Status |
|---|---|---|---|
| `scanner/` | Trading | Python | Active (v6.0+) |
| `scanner-v2/` | Trading | Python | Active (enhanced C&H) |
| `scanner-v3/` | Trading | Python | **Active (v3 production)** |
| `weekly-swing-setup-scanner/` | Trading | Python | Redundant — candidate for archival |
| `earnings-momentum-scanner/` | Trading | Python | Active (PEAD strategy) — tracked by root git |
| `earnings-scanner/` | Trading | Python | **Duplicate clone** of earnings-momentum-scanner (byte-identical, separate GitHub remote). Candidate for removal. |
| `scanner-training/` | Trading | Python | Support (validation/tuning) |
| `chart-visualizer/` | Trading | Python | Support (charts from v2 output) |
| `_old-scanner/`, `_archived/` | Trading | Python | Archived (v5.0 / v6.0 frozen) |
| `job-hunter/` | Career | Python + Chrome ext | Active (personal tool) |
| `tableflow/` | SaaS | Node.js + Docker | Flagship — 9/14 services production-ready |
| `auth-service/` | SaaS | TypeScript + Express | Standalone (may supersede tableflow's) |
| `notification-service/` | SaaS | JS + Express + Bull | Standalone (may supersede tableflow's) |
| `portfolio/` | Personal | Next.js 14 | Static site |

---

## Domain 1 — Stock Scanners (NSE India)

All scanners target NSE (Indian stock market) swing trading setups. Data source is `jugaad-data` (NSE native) with `yfinance` fallback. Output: CSV in `results/` + optional charts + optional Telegram alerts.

### Shared conventions
- Python projects. Run from project root.
- `.env` files (90 bytes) in scanner projects contain Telegram bot tokens — **do not commit**.
- Cache: 8-hour TTL disk cache in `cache/`.
- Stock universe files: `backbone50.txt` (62 curated), `nifty500.txt`, `nifty200.txt`, or full NSE EQ list via `data/nse_eq.py`.
- Most projects **lack `requirements.txt`** — see per-project notes.

### `scanner/` — Main swing screener (v6.0+)
Modular: `engine/`, `patterns/`, `scoring/`, `portfolio/`, `utils/`, `data/`, `backtester/`.
Patterns: Cup & Handle (D/W/M), Double Bottom, Darvas Box, Flags, Breakout, Retest, Compression, Wedge, Break & Retest, Triangle, S&R, Channel. Multi-timeframe (D/W/M/4H). Sector rotation engine in `utils/sector_rotation.py`.

```powershell
# No .bat in this project — run engine directly
python engine/scanner.py
python backtest.py
python backtest_historical.py
python backtest_optimize.py
```

### `scanner-v2/` — Enhanced scanner (diagonal neckline, monthly TF, T1/T2)
Streamlined: `scanner.py`, `daily_scan.py`, `gen_charts.py`, `telegram_notify.py`, `check_perf.py`.
C&H hit rate improved 52% → 95% on 204-sample ground truth. Status tiers: WATCH / NEAR / BREAKOUT. Two targets (T1=60% of move, T2=full move).

```powershell
# Daily morning scan (sector heat + backbone 50 + hot sectors)
.\Daily Scan.bat            # runs: python daily_scan.py --top 15

# Weekly scan
.\run_weekly.bat            # runs scanner.py + gen_charts.py + telegram_notify.py

# Performance check
python check_perf.py
```

### `scanner-v3/` — Production swing scanner (v3)
Built on scanner-v2 (proven +2.7% expectancy/trade, 35% win rate, 3:1 R:R over 97 closed trades). Production swing scanner targeting NSE. **GitHub: https://github.com/karthik0419/scanner-v3**
Has `requirements.txt`, `backbone50.txt`, `nifty500.txt`, `COMPARISON_REPORT.md`. Improvements driven by performance verification of 414 picks (May-Jul 2026).

**9 key improvements over v2:**
1. **ATR-based stop loss (default)** — v2 avg SL loss was -6.5%; earnings-scanner proved -3% stops work. Tighter stops = smaller losses. (`--sl-mode atr`, original v2 stops available via `--sl-mode original`.)
2. **Double Bottom promoted** — 100% win rate (11W/0L) across scanners; score bonus 18 → 28.
3. **Channel Breakout tightened** — 24% win rate was dragging performance; volume gate 1.3x → 1.5x, RSI < 75, R:R >= 1.5.
4. **Cup & Handle (Weekly) promoted** — 50% win rate in `scanner/`; score bonus 25 → 28.
5. **Price range filter** — retail-friendly high-momentum stocks; `--min-price 100 --max-price 400`.
6. **Self-contained sector rotation** — no dependency on `scanner/`; `utils/sector_rotation_v3.py` with 568+ stock-to-sector mappings from NSE official index constituents.
7. **Bearish / short mode** — NSE Heat Map strategy: find weak sectors, short weakest stocks; `--bearish` flag.
8. **`requirements.txt`** — was missing in v2; now reproducible installs.
9. **C&H Weekly detector fixed (2026-07-17)** — was -0.56% avg P&L (losing money). Root cause: handle_bars=12 allowed 3-month downtrends as "handles". Fixed to Bulkowski's classical definition: handle_bars=4, max_depth=0.50, near_pct=0.08/0.15, handle_depth_ratio=0.50, volume_lookback=52. Now +0.76% avg P&L on 746 out-of-sample trades. Parameterized so daily/monthly detectors are unaffected.

**Additional improvements (2026-07-18):**
10. **Sector classification fixed** — was 47% wrong (14/30 scan picks misclassified). Now uses 3-layer lookup: NSE official index constituents (568 stocks) → yfinance `industry` field (granular, 80+ mappings) → yfinance `sector` field (coarse fallback). 30/30 correct on test picks. Run `python utils/build_sector_map.py` to refresh.
11. **Daily scan smart universe** — was only scanning ~600 stocks (Nifty 500 + hardcoded ~15/sector). Now scans Backbone 50 + Nifty 500 + weekly picks + ALL stocks in today's hot sectors (50-100+ per sector from NSE sector map). `--full` flag scans complete NSE EQ (~2000+). Parallel thread pool (`--workers 8`, 4-8x faster).
12. **Timeframe tracking + filter** — every pattern result now includes `timeframe` column (Daily/Weekly/Monthly). `--timeframe daily|weekly|monthly` flag filters to one timeframe for manual chart verification.
13. **Automated Telegram notifications** — scanner.py and daily_scan.py auto-send Telegram on completion. `--no-notify` to opt out.

**Backtest results (post-fix, validated on two datasets):**

| Dataset | Stocks | Trades | Win rate | Avg loss | Expectancy | Max drawdown |
|---|---|---|---|---|---|---|
| backbone50 (in-sample) | 51 | 860 | 42.7% | -5.12% | +2.03% | -69.1% |
| nifty200 (out-of-sample) | 178 | 2903 | 42.6% | -4.76% | +1.37% | -84.6% |

- v3 and v2 are now **tied on expectancy** (the pre-fix gap is eliminated)
- v3 has tighter avg loss than v2 (-4.76% vs -4.89% on nifty200)
- **Max drawdown is worse for v3** — open issue, needs investigation before live trading with real capital
- C&H Weekly fix generalizes (not overfit): +0.87% in-sample, +0.76% out-of-sample
- Full breakdown in `COMPARISON_REPORT.md`

```powershell
pip install -r requirements.txt

# Full weekly scan (top 30 setups)
python scanner.py

# Top 50, min score 50
python scanner.py --top 50 --min-score 50

# Retail filter: only stocks between 100-400 Rs
python scanner.py --min-price 100 --max-price 400

# Original v2 stop loss (wider, for comparison)
python scanner.py --sl-mode original

# Bearish scan: find short setups in weak sectors
python scanner.py --bearish

# Quick test (50 stocks only)
python scanner.py --test

# Daily morning scan (smart universe: Backbone + Nifty500 + hot sector stocks)
python daily_scan.py --top 15

# Daily scan - full NSE EQ universe (~2000+ stocks, ~10-15 min)
python daily_scan.py --full --workers 10

# Daily scan with price filter
python daily_scan.py --min-price 100 --max-price 400

# Daily bearish scan
python daily_scan.py --bearish

# Scan by timeframe (for manual chart verification)
python scanner.py --timeframe weekly    # weekly patterns only
python scanner.py --timeframe daily     # daily patterns only
python scanner.py --timeframe monthly   # monthly patterns only

# Refresh sector mapping (run monthly to pick up new IPOs)
python utils/build_sector_map.py

# Weekly scan + charts + Telegram
.\run_weekly.bat

# Daily scan
.\Daily Scan.bat

# Backtest v3 vs v2 comparison (backbone50, ~5 min)
python compare_backtest.py --stocks backbone50.txt --years 2 --min-score 40

# Backtest on nifty200 (out-of-sample, ~15 min)
python compare_backtest.py --stocks nifty200.txt --years 2 --min-score 40

# Paper tracker — track live picks vs backtest expectancy
python paper_tracker.py init                              # init from latest scan CSV
python paper_tracker.py update                            # fetch current prices, update status
python paper_tracker.py update --price NATCOPHARM.NS=980  # manual price override
python paper_tracker.py status                            # full status + closed trades summary
python paper_tracker.py summary                           # one-line summary
python paper_tracker.py reset                             # delete tracker (careful)
```

**Key files:**
- `scanner.py` — main weekly scanner (v3 engine)
- `daily_scan.py` — daily morning scanner (volume + sectors)
- `gen_charts.py` — chart generator (daily/weekly/monthly per pick)
- `telegram_notify.py` — Telegram alerts (top 10 picks)
- `paper_tracker.py` — paper trade tracker for live validation
- `compare_backtest.py` — v3 vs v2 side-by-side backtest comparison
- `backtest.py` — standalone v3 backtest
- `COMPARISON_REPORT.md` — full backtest results + pattern breakdown
- `backbone50.txt` — 51 curated momentum stocks (in-sample)
- `nifty200.txt` — 200 large-cap stocks (out-of-sample test set)
- `config/settings.py` — configuration constants
- `utils/sector_rotation_v3.py` — self-contained sector rotation (bullish + bearish)

### `weekly-swing-setup-scanner/` — Simplified weekly scanner
Subset of scanner-v2: no monthly TF, no WATCH tier, no diagonal neckline, single target. **Candidate for archival** — no unique features vs scanner-v2.

```powershell
.\run_weekly.bat            # runs scanner.py + gen_charts.py + telegram_notify.py
```

### `earnings-momentum-scanner/` — PEAD / post-earnings momentum (v3)
Different strategy: scans for post-earnings pullback entries. Uses `screener.in` for earnings data + `scipy` for profit projection. Modes: weekly (588 stocks), discovery (2131 stocks, ~90 min), daily (top sectors + backbone). **Has `requirements.txt`.** This is the project tracked by the root git repo (remote: `karthik0419/earnings-momentum-scanner`).

> **Note:** `earnings-scanner/` is a byte-identical duplicate clone (remote: `karthik0419/earnings-scanner`). Same files, same content, separate GitHub repo. Candidate for removal — decide which GitHub repo is canonical and delete the other local clone.

```powershell
cd earnings-momentum-scanner
.\run_scanner.bat           # interactive: 1=weekly, 2=discovery, 3=daily
python scanner.py --mode weekly --top 30 --min-score 35 --delay 2.0 --workers 6
python scanner.py --mode discovery --top 50 --min-score 40 --delay 2.5 --workers 4
python scanner.py --mode daily --top 20 --min-score 40 --delay 1.0 --workers 8

.\run_backtest.bat          # backtester
python test_pipeline.py     # end-to-end smoke test

pip install -r requirements.txt
```

### `scanner-training/` — Pattern validation & tuning
Parses Telegram trade-chat HTML export (`E:/TRADE TEam CHAT`) into ground truth, validates tuned detectors vs production, gap analysis. Tuned patterns in `tuned_patterns/` feed back into `scanner/` and `scanner-v2/`. Sector rotation engine was built here.

```powershell
python scripts/parse_telegram.py
python scripts/extract_setups.py
python scripts/validate_tuned.py
```

### `chart-visualizer/` — Standalone chart generator
Reads scanner-v2 CSV output, produces annotated candlestick charts (Daily 120 bars / Weekly 60 bars) with pattern overlays. **Has `requirements.txt`.**

```powershell
.\run_visualizer.bat
python visualize.py
pip install -r requirements.txt
```

### `_old-scanner/`, `_archived/` — Archived versions
Frozen v6.0 and v5.0. Reference only. Do not modify.

---

## Domain 2 — Job Hunter

Automated job application system for Kartik's DevOps/SRE profile. Scrapes LinkedIn, Naukri, Indeed, Instahyre, + 24 Finnish companies → scores → applies via Workday/LinkedIn Easy Apply/Oracle ORC → SQLite tracker → Telegram alerts.

### ⚠️ Security notes
- `.env` contains real credentials (Telegram bot token, LinkedIn/Naukri/Workday passwords). **Never commit, never share publicly.**
- Phone `8149927963` is hardcoded in multiple files.
- Two different emails appear in profile (`bandewarkarthik@gmail.com` vs `kartikbandewar1911@gmail.com`).
- Chrome extension `content.js` reportedly has a password in default profile.

### Commands
```powershell
pip install -r requirements.txt

# Manual run with Telegram approval workflow
python main.py

# Fully automated (auto-apply at score >=70)
python automate.py --limit 15

# Apply to a specific job URL
python apply_now.py <url>

# Install Windows Task Scheduler job (daily 9 AM)
python scheduler_setup.py
# Manual trigger:  schtasks /Run /TN "JobHunterAutoApply"
# Remove:          schtasks /Delete /TN "JobHunterAutoApply" /F

.\run_daily.bat             # runs automate.py
```

### Structure
- `scrapers/` — LinkedIn, Naukri, Indeed, Instahyre, Finland
- `engine/scorer.py` — role/skills/location/experience scoring (max 100)
- `applicator/` — Workday, LinkedIn Easy Apply, Oracle ORC
- `notifier/telegram_bot.py` — inline buttons: Apply/Skip/Shortlist
- `tracker/tracker.py` — SQLite (`jobs` table, dedup by job_id)
- `chrome-extension/` — Manifest V3, manual form-fill for 9 ATS platforms
- `profile/profile.py` — target roles, locations, skills, exclusions

---

## Domain 3 — TableFlow (Restaurant POS SaaS)

Microservices architecture: 14 services + PostgreSQL + Redis + RabbitMQ + nginx + Prometheus/Grafana. Two deploy modes: Docker Compose, or Windows installer (Inno Setup, bundles Node.js + PostgreSQL + nginx).

### ⚠️ Known issues
- **`DATABASE_SCHEMA_COMPLETE.sql` is referenced in `docker-compose.yml` but does not exist** — compose will fail on the Postgres init step. Each service manages its own schema instead.
- **Customer Service uses in-memory Map storage** — data lost on restart. `pg` is in `package.json` but unused. **Critical bug.**
- **4 services are skeletons**: Aggregator, Online Ordering, Staff, Notification (in tableflow).
- **No service-to-service auth** on most services.
- **Frontend uses in-browser Babel** (React via CDN) — fine for demo, slow for production.

### Commands — Docker (full stack)
```powershell
cd tableflow
docker-compose up -d                          # start all 18 containers
docker-compose down                           # stop
docker-compose logs -f auth-service           # tail logs
# Frontend:      http://localhost:8080
# Grafana:       http://localhost:3000
# Prometheus:    http://localhost:9090
# RabbitMQ Mgmt: http://localhost:15672
```

### Commands — Windows native
```powershell
cd tableflow
.\install.bat                                 # one-click installer
.\Start TableFlow.bat                         # start all services
.\Stop TableFlow.bat                          # stop
.\Backup TableFlow.bat                        # DB backup
.\Restore TableFlow.bat                       # DB restore
.\Update TableFlow.bat                        # update
.\Add Waiter Account.bat                      # create staff account
.\Network Info.bat                            # show LAN IP for waiter app
```

### Service ports
| Port | Service | Status |
|---|---|---|
| 5001 | Auth | ✅ Production-ready |
| 5002 | Order (state machine + WebSocket) | ✅ Production-ready |
| 5003 | Menu (full-text search, image upload) | ✅ Production-ready |
| 5004 | Inventory (ledger, FIFO/LIFO) | ✅ Production-ready |
| 5005 | Billing (GST, double-entry accounting) | ✅ Production-ready |
| 5006 | Table (floors, reservations, QR) | ✅ Production-ready |
| 5007 | KDS (kitchen display, WebSocket) | ✅ Production-ready |
| 5008 | Delivery | ⚠️ Partial (skeleton controllers) |
| 5009 | Customer (CRM, loyalty, RFM) | ⚠️ In-memory DB — critical |
| 5010 | Report (PDF/Excel/CSV export) | ✅ Functional |
| 5011 | Aggregator (Zomato/Swiggy/UberEats) | ❌ Skeleton |
| 5012 | Online Ordering | ❌ Skeleton |
| 5013 | Staff | ❌ Skeleton |
| 5014 | Notification | ❌ Skeleton |
| 8080 | nginx (frontend gateway) | ✅ |
| 5432 | PostgreSQL | ✅ |
| 6379 | Redis | ✅ |
| 5672/15672 | RabbitMQ | ✅ |
| 9090/3000 | Prometheus / Grafana | ✅ |

### Standalone services (workspace root — may supersede tableflow-internal versions)
These are **more polished, TypeScript/Sequelize** versions vs the JS/raw-pg ones inside `tableflow/`. Decide which to keep and delete the other to avoid divergence.

#### `auth-service/` (TypeScript, Express, Sequelize, Redis, JWT, MFA, OAuth2)
```powershell
cd auth-service
npm install
npm run dev          # ts-node src/index.ts
npm run build        # tsc -> dist/
npm start            # node dist/index.js
npm test             # jest
npm run lint         # eslint
npm run migrate      # node scripts/migrate.js
# Docker: docker-compose up  (brings up Postgres + Redis + auth)
```

#### `notification-service/` (JS, Express, Bull, Redis, Twilio, SendGrid, Firebase)
```powershell
cd notification-service
npm install
npm run dev          # nodemon src/server.js
npm start            # node src/server.js
npm test             # jest --coverage
npm run lint         # eslint src --fix
npm run queue:stats  # view Bull queue stats
npm run queue:clean  # clean failed jobs
```

---

## Domain 4 — Portfolio

Static Next.js 14 site (App Router, Tailwind, dark/terminal theme). Static export — no backend.

```powershell
cd portfolio
npm install
npm run dev          # http://localhost:3000
npm run build
npm run export       # static export to out/
```

---

## Cross-Cutting Notes

### Secrets hygiene
- Scanner `.env` files (Telegram tokens) and `job-hunter/.env` (platform credentials) are on disk. Root `.gitignore` excludes `.env` but the files exist locally.
- Before publishing any of this: scrub hardcoded phone numbers, emails, passwords, and tokens.

### Code duplication (highest-priority refactor)
- Pattern detectors, data loaders, chart generators, and Telegram notifiers are copy-pasted across `scanner/`, `scanner-v2/`, `scanner-v3/`, `weekly-swing-setup-scanner/`. `scanner-v3/` is the canonical version — others should be archived or refactored to import from it.
- `auth-service` and `notification-service` exist both at workspace root (TypeScript) and inside `tableflow/` (JS). Pick one of each.

### Missing tests
- Only `earnings-scanner/test_pipeline.py`, `auth-service/__tests__/`, and `notification-service/tests/` have any tests. Everything else is untested.

### Missing dependency manifests
- `scanner/`, `scanner-v2/`, `weekly-swing-setup-scanner/`, `scanner-training/` have no `requirements.txt`. Add one per project.

### Suggested cleanup order
1. Fix TableFlow Customer Service storage (in-memory → PostgreSQL) — critical bug.
2. Remove dead `DATABASE_SCHEMA_COMPLETE.sql` reference from `tableflow/docker-compose.yml`.
3. Consolidate scanners into `scanner-v3/` as the canonical scanner package with shared modules; archive `_old-scanner`, `_archived`, `weekly-swing-setup-scanner`.
4. Pick one `auth-service` and one `notification-service`; delete the other.
5. Scrub secrets from `job-hunter/` and scanner `.env` files.
6. Add `requirements.txt` to all Python projects.
