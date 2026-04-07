"""InvestorRadar Flask REST API.

Exposes financial data endpoints that the React frontend consumes.
All data is sourced from SEC EDGAR + yfinance. Zero paid API keys required.
"""

import os
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
from sec_engine import get_sec_tickers_list

app = Flask(__name__)
CORS(app)


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
      - q: optional search string (ticker or name) to restrict results
      - sector: sector filter, "All" to ignore
      - dividends_only: "1" | "true"
      - market_cap_min/max, pe_min/max, volume_min/max, price_min/max
      - limit: max rows evaluated/returned (default 250)
    """

    def f(name):
        raw = request.args.get(name)
        if raw is None or raw == "":
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    q = request.args.get("q", "").strip().upper()
    sector = request.args.get("sector", "All").strip()
    dividends_only = request.args.get("dividends_only", "").strip().lower() in ("1", "true", "yes")
    limit = int(request.args.get("limit", "250"))

    # Keep the universe intentionally bounded. For broader coverage, extend this list server-side.
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
    )

    if q:
        # Allow quick search refine without new endpoints.
        rows = [
            r
            for r in rows
            if q in (r.get("ticker") or "")
            or q in (r.get("company_name") or "").upper()
        ]

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

    tickers = get_sec_tickers_list()
    results = []
    for t in tickers:
        if query in t["ticker"] or query in t["name"].upper():
            results.append(t)
        if len(results) >= 10:
            break
    return jsonify(results)


@app.route("/api/news/<ticker>")
def news(ticker):
    """Returns recent news for a ticker."""
    data = get_news(ticker.upper())
    return jsonify(data)


if __name__ == "__main__":
    print("InvestorRadar API starting on http://localhost:5000")
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", debug=True, port=port)
