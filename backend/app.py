"""InvestorRadar Flask REST API.

Exposes financial data endpoints that the React frontend consumes.
All data is sourced from SEC EDGAR + yfinance. Zero paid API keys required.
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
    get_screener_results,
)
from sec_engine import get_sec_tickers_list, get_sp500_constituents
from universe_sync import (
    ensure_stock_universe_ready,
    search_stock_universe,
    sync_stock_universe,
)

app = Flask(__name__)
CORS(app)

MEGA_CAP_TICKERS = (
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "BRK-B", "TSLA",
    "AVGO", "LLY", "JPM", "V", "WMT", "XOM", "MA", "COST",
    "NFLX", "JNJ", "PG", "ORCL", "HD", "ABBV", "BAC", "KO",
    "PM", "CVX", "CRM", "UNH", "CSCO", "IBM",
)


def _normalize_yahoo_symbol(symbol):
    return (
        (symbol or "")
        .strip()
        .upper()
        .replace(".", "-")
        .replace("/", "-")
        .replace(" ", "")
    )


def _search_public_tickers(query, *, limit=150):
    """Return a bounded list of matching public-company tickers from local DB."""
    q = (query or "").strip()
    if not q:
        return []

    ensure_stock_universe_ready()
    results = search_stock_universe(q, limit=limit)
    if results:
        return [
            {
                "ticker": row["ticker"],
                "company_name": row["company_name"],
            }
            for row in results
        ]

    # Fallback to SEC data if the local database is unavailable or stale.
    ranked = []
    q_upper = q.upper()
    for item in get_sec_tickers_list():
        ticker = _normalize_yahoo_symbol(item.get("ticker"))
        name = (item.get("name") or "").upper()
        if not ticker:
            continue
        if ticker == q_upper:
            score = 0
        elif ticker.startswith(q_upper):
            score = 1
        elif name.startswith(q_upper):
            score = 2
        elif q_upper in ticker or q_upper in name:
            score = 3
        else:
            continue
        ranked.append((score, len(ticker), ticker, item.get("name") or ticker))

    ranked.sort(key=lambda x: (x[0], x[1], x[2]))
    return [
        {"ticker": ticker, "company_name": company_name}
        for _, _, ticker, company_name in ranked[:limit]
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

    universe = request.args.get("universe", "sp500").strip().lower()
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
    else:
        # Keep a fallback "popular" universe for low-latency demos.
        scan_list = (
            "AAPL", "MSFT", "NVDA", "TSLA", "AMD", "GOOGL", "AMZN", "META",
            "NFLX", "JPM", "V", "WMT", "DIS", "INTC", "BA", "PYPL",
            "CRM", "UBER", "COIN", "PLTR", "AVGO", "ORCL", "ADBE", "QCOM",
            "TXN", "MU", "CSCO", "SHOP", "SNOW", "PANW", "CRWD", "NOW",
            "XOM", "CVX", "COP", "PFE", "JNJ", "MRK", "UNH", "ABBV",
            "GS", "MS", "BAC", "C", "MA", "AXP", "KO", "PEP",
        )

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
    if results:
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

    tickers = get_sec_tickers_list()
    fallback = []
    for t in tickers:
        if query in t["ticker"] or query in t["name"].upper():
            fallback.append(t)
        if len(fallback) >= 10:
            break
    return jsonify(fallback)


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
