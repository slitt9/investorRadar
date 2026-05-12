"""InvestorRadar Flask REST API.

Exposes financial data endpoints that the React frontend consumes.
Screener rows are served from a local SQLite snapshot (refresh via scripts);
other routes may still use SEC EDGAR + yfinance on demand.
"""

import os
import sys
from flask import Flask, request, jsonify
from flask_cors import CORS
from metrics import (
    calculate_metrics,
    get_historical_data,
    get_sparkline_data,
    get_movers,
    get_indices,
    get_markets_snapshot,
    get_sector_performance,
    get_news,
)
from db import get_db
from refresh_quotes import refresh_quotes
from screener_db import get_screener_results
from screener_hydrate import hydrate_screener_rows
from sec_engine import get_sp500_constituents
from universe_config import MEGA_CAP_TICKERS, POPULAR_TICKERS
from universe_sync import (
    ensure_stock_universe_ready,
    get_searchable_equity_tickers,
    search_stock_universe,
    sync_stock_universe,
)

app = Flask(__name__)
CORS(app)


def _search_public_tickers(query, *, limit=150):
    """Return a bounded list of matching public-company tickers from local DB."""
    q = (query or "").strip()
    if not q:
        return []

    ensure_stock_universe_ready()
    results = search_stock_universe(q, limit=limit)
    return [
        {"ticker": row["ticker"], "company_name": row["company_name"]}
        for row in results
    ]


@app.route("/api/quote/<ticker>")
def quote(ticker):
    """Returns locally calculated metrics for a ticker."""
    data = calculate_metrics(ticker.upper())
    if data["price"] is None:
        return jsonify({"error": f"No data found for {ticker}"}), 404
    return jsonify(data)


@app.route("/api/sparkline/<ticker>")
def sparkline(ticker):
    """Returns 30-day closing price array for sparkline charts."""
    data = get_sparkline_data(ticker.upper())
    return jsonify(data)


@app.route("/api/history/<ticker>")
def history(ticker):
    """Returns OHLCV historical data. Query params: period, interval."""
    period = request.args.get("period", "1y")
    interval = request.args.get("interval", "1d")
    data = get_historical_data(ticker.upper(), period=period, interval=interval)
    return jsonify(data)


@app.route("/api/movers")
def movers():
    """Returns top gainers and losers from popular stocks."""
    data = get_movers()
    return jsonify(data)


def _tickers_missing_snapshot_price(scan_list: tuple[str, ...], *, max_fix: int) -> list[str]:
    """First N tickers in scan_list with no priced row in stock_snapshot."""
    if not scan_list:
        return []
    out: list[str] = []
    with get_db() as conn:
        for t in scan_list:
            if len(out) >= max_fix:
                break
            row = conn.execute(
                "SELECT 1 FROM stock_snapshot WHERE ticker = ? AND price IS NOT NULL",
                (t,),
            ).fetchone()
            if not row:
                out.append(t)
    return out


@app.route("/api/screener")
def screener():
    """Returns screener rows for a bounded universe.

    Query params:
      - universe: "sp500" | "mega" | "popular" (default: sp500)
      - q: optional search string (ticker or name) to restrict results
      - sector: sector filter, "All" to ignore
      - dividends_only: "1" | "true"
      - market_cap_min/max, pe_min/max, volume_min/max, price_min/max
      - limit: max rows returned (default 250)
    """

    def f(name):
        raw = request.args.get(name)
        if raw is None or raw == "":
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    universe = request.args.get("universe", "all").strip().lower()
    all_cap = int(os.environ.get("SCREENER_UNIVERSE_MAX", "4000"))
    q = request.args.get("q", "").strip().upper()
    sector = request.args.get("sector", "All").strip()
    dividends_only = request.args.get("dividends_only", "").strip().lower() in ("1", "true", "yes")
    limit = int(request.args.get("limit", "250"))

    meta_source = None

    if q:
        matches = _search_public_tickers(q, limit=150)
        scan_list = tuple(m["ticker"] for m in matches)
    elif universe in ("sp500", "mega"):
        constituents = get_sp500_constituents()
        if universe == "mega":
            mega_set = set(MEGA_CAP_TICKERS)
            constituents = [c for c in constituents if c.get("ticker") in mega_set]
        scan_list = tuple(c["ticker"] for c in constituents)
        meta_source = "sp500"
    elif universe in ("all", "equities", "extended"):
        ensure_stock_universe_ready()
        scan_list = tuple(get_searchable_equity_tickers(limit=all_cap))
    else:
        scan_list = POPULAR_TICKERS

    if q and os.environ.get("SCREENER_ON_DEMAND_QUOTES", "1").lower() in ("1", "true", "yes"):
        missing = _tickers_missing_snapshot_price(scan_list, max_fix=20)
        if missing:
            try:
                refresh_quotes(missing)
            except Exception:
                pass

    rows = get_screener_results(
        tickers=scan_list,
        market_cap_min=f("market_cap_min"),
        market_cap_max=f("market_cap_max"),
        pe_min=f("pe_min"),
        pe_max=f("pe_max"),
        volume_min=f("volume_min"),
        volume_max=f("volume_max"),
        price_min=f("price_min"),
        price_max=f("price_max"),
        sector=sector,
        dividends_only=dividends_only,
        limit=limit,
        meta_source=meta_source,
    )

    # Default sort: pct_change desc (matches UI default).
    rows.sort(key=lambda r: (r.get("pct_change") is None, -(r.get("pct_change") or 0.0)))
    rows = hydrate_screener_rows(rows)
    return jsonify(rows)


@app.route("/api/indices")
def indices():
    """Returns current values for major market indices."""
    data = get_indices()
    return jsonify(data)


@app.route("/api/markets")
def markets():
    """Returns a multi-asset market snapshot (futures, global, crypto)."""
    data = get_markets_snapshot()
    return jsonify(data)


@app.route("/api/sectors")
def sectors():
    """Returns top performing sectors from the movers scan list."""
    data = get_sector_performance()
    return jsonify(data)


@app.route("/api/search")
def search():
    """Searches SEC ticker database. Query param: q."""
    query = request.args.get("q", "").upper().strip()
    if not query or len(query) < 1:
        return jsonify([])
    ensure_stock_universe_ready()
    results = search_stock_universe(query, limit=10)
    return jsonify(
        [
            {
                "ticker": row["ticker"],
                "name": row["company_name"],
                "cik": row.get("cik"),
                "exchange": row.get("exchange"),
                "security_type": row.get("security_type"),
            }
            for row in results
        ]
    )


@app.route("/api/admin/universe/sync", methods=["POST"])
def sync_universe():
    """Manually refresh the local stock universe database."""
    force = request.args.get("force", "").strip().lower() in ("1", "true", "yes")
    result = sync_stock_universe(force=force)
    return jsonify(result)


@app.route("/api/news/<ticker>")
def news(ticker):
    """Returns recent news for a ticker."""
    data = get_news(ticker.upper())
    return jsonify(data)


if __name__ == "__main__":
    print("InvestorRadar API starting on http://localhost:5000")
    port = int(os.environ.get("PORT", "5000"))
    # Werkzeug's file watcher + reloader can hit WinError 10038 on Windows (bad socket in select()).
    # Opt back in with FLASK_USE_RELOADER=1 if you accept occasional reloader crashes.
    use_reloader = True
    if sys.platform == "win32":
        use_reloader = os.environ.get("FLASK_USE_RELOADER", "").lower() in ("1", "true", "yes")
    app.run(host="0.0.0.0", debug=True, port=port, use_reloader=use_reloader)
