# InvestorRadar

Stock screener and dashboard: **Next.js** frontend and **Flask** API. The screener table reads from a **local SQLite snapshot** so filters do not hit Yahoo on every request. Detail routes (quote, charts, markets) may still fetch **SEC EDGAR** and **yfinance** on demand.

No paid API keys are required.

## Requirements

- Python 3.11+ (virtualenv recommended)
- Node.js 20+ (for the frontend)

## Backend

```bash
cd backend
pip install -r requirements.txt
python app.py
```

API base URL defaults to `http://localhost:5000`.

### Environment

| Variable | Purpose |
|----------|---------|
| `INVESTOR_RADAR_DB_PATH` | Optional path to SQLite file (default: `backend/data/investorradar.db`) |
| `UNIVERSE_STALE_HOURS` | Re-sync Nasdaq/SEC listing data if older than this many hours (default: `72`) |
| `SCREENER_UNIVERSE_MAX` | Max tickers when API `universe=all` (default: `4000`) |
| `REFRESH_ALL_CAP` | Max tickers for `refresh_* --universe all` (default: `2500`) |
| `QUOTE_REFRESH_SKIP_VALUATION` | Set `1` to skip cap/P/E enrichment during `refresh_quotes` (default: enrich on) |
| `QUOTE_VALUATION_SLEEP` | Seconds between per-ticker valuation calls (default: `0.08`) |
| `PORT` | Flask listen port (default: `5000`) |
| `FLASK_USE_RELOADER` | On Windows, set `1` to enable the debug reloader (can be unstable). |

### Local database and refresh jobs

1. **Universe** (`stock_universe`): Nasdaq Trader symbol directories + SEC `company_tickers.json` (CIK, titles). Populated on first search if empty, or manually:

   ```bash
   cd backend
   python refresh_universe.py --force
   ```

2. **Screener snapshots** (`stock_snapshot`): Run after the universe exists:

   ```bash
   cd backend
   python refresh_quotes.py --universe sp500
   python refresh_fundamentals.py --universe sp500
   ```

   `refresh_quotes` also fills **market cap** (Yahoo `fast_info`) and **P/E** (price ÷ SEC diluted EPS when available) so the grid shows cap/P/E closer to the detail view. Use `--no-valuation` or `QUOTE_REFRESH_SKIP_VALUATION=1` to skip that (faster).

   Broader US listings (thousands of tickers; longer runs):

   ```bash
   python refresh_quotes.py --universe all
   python refresh_fundamentals.py --universe all --max 800
   ```

   Or one shot (intended for **cron** / **Task Scheduler**, e.g. ~3× per US trading day):

   ```bash
   cd backend
   python scheduled_refresh.py
   ```

   Windows helper: `backend/scripts/scheduled_refresh.ps1`  
   Unix helper: `backend/scripts/scheduled_refresh.sh`

   Optional env for `scheduled_refresh.py`: `REFRESH_UNIVERSE_MODE` (`sp500` \| `mega` \| `popular`), `SKIP_UNIVERSE_SYNC`, `FORCE_UNIVERSE_SYNC`.

3. **Admin HTTP** (while the API is running): `POST /api/admin/universe/sync?force=true` refreshes listings only (not quotes/fundamentals).

The SQLite file is gitignored (`backend/data/*.db`).

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_BASE_URL` if the API is not on `http://localhost:5000`.

## Data sources

- **Universe:** [Nasdaq Trader symbol directory](https://www.nasdaqtrader.com/trader.aspx?id=SymbolDirDefs), [SEC company_tickers.json](https://www.sec.gov/files/company_tickers.json)
- **Screener snapshot quotes:** batched yfinance (refresh scripts)
- **Screener fundamentals:** SEC company facts where possible; Yahoo metadata as fallback for sector/industry and gaps

Use a descriptive `User-Agent` when calling `sec.gov` (already set in the backend).
