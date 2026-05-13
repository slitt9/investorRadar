"""Local financial metric calculation engine.

Combines live price data from yfinance with fundamental data
from SEC EDGAR to calculate metrics without any paid API keys.
"""

import yfinance as yf
from sec_engine import get_cik_for_ticker, get_sec_facts, extract_latest_sec_fact
from cache import cached
from db import get_db

# Yahoo ties requests to one session/crumb; bursty parallel calls often return 401 / Invalid Crumb.
yf.config.network.retries = 3


def _clamp(n, lo=0.0, hi=100.0):
    return max(lo, min(hi, n))


def _safe_float(value):
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_sec_fact(facts, *tags, unit="USD"):
    for tag in tags:
        value = extract_latest_sec_fact(facts, tag, unit=unit)
        if value is not None:
            return value
    return None


def _snapshot_metrics(ticker):
    try:
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT
                    market_cap, pe_ratio, sector, industry, dividend_yield,
                    fifty_two_week_high, fifty_two_week_low, company_name,
                    radar_pulse
                FROM stock_snapshot
                WHERE ticker = ?
                """,
                (ticker.upper(),),
            ).fetchone()
            return dict(row) if row else {}
    except Exception:
        return {}


def _persist_radar_pulse_if_missing(ticker, radar_pulse):
    if radar_pulse is None:
        return
    try:
        with get_db() as conn:
            conn.execute(
                """
                UPDATE stock_snapshot
                SET radar_pulse = COALESCE(radar_pulse, ?)
                WHERE ticker = ?
                """,
                (int(radar_pulse), ticker.upper()),
            )
    except Exception:
        pass


def compute_radar_pulse(metrics):
    """Compute Radar Stock Pulse (0-100) from available metrics.

    Formula:
      Pulse = 0.30*Growth + 0.25*Profitability + 0.25*DebtHealth + 0.20*IndustryEdge
    """

    # Growth score: quarterly revenue growth (%) scaled.
    growth_pct = metrics.get("quarterly_revenue_growth")
    if growth_pct is None:
        growth = 50.0
    else:
        # -10% -> 0, 0% -> 40, 20% -> 80, 50%+ -> 100
        if growth_pct <= -10:
            growth = 0.0
        elif growth_pct <= 0:
            growth = (growth_pct + 10) * 4.0  # 0..40
        elif growth_pct <= 20:
            growth = 40.0 + (growth_pct / 20.0) * 40.0  # 40..80
        else:
            growth = 80.0 + _clamp((growth_pct - 20) / 30.0 * 20.0, 0.0, 20.0)  # 80..100

    # Profitability score: profit margin (0..0.30) mapped to 0..100, negatives -> 0.
    pm = metrics.get("profit_margin")
    if pm is None:
        profitability = 50.0
    else:
        profitability = _clamp((pm / 0.30) * 100.0, 0.0, 100.0)

    # Debt health score: lower liabilities/assets is better.
    assets = metrics.get("assets")
    liabilities = metrics.get("liabilities")
    if assets is None or liabilities is None or assets == 0:
        debt_health = 50.0
    else:
        ratio = liabilities / assets
        # ratio <= 0.30 -> 100, ratio >= 0.85 -> 0 (linear)
        if ratio <= 0.30:
            debt_health = 100.0
        elif ratio >= 0.85:
            debt_health = 0.0
        else:
            debt_health = _clamp((0.85 - ratio) / (0.85 - 0.30) * 100.0, 0.0, 100.0)

    # Industry edge score: sector preference ordering.
    sector = (metrics.get("sector") or "").strip()
    ranking = ["Energy", "Industrials", "Technology", "Financials", "Healthcare", "Consumer"]
    if sector in ranking:
        idx = ranking.index(sector)
        industry_edge = 100.0 - idx * 10.0  # 100,90,...
    else:
        industry_edge = 50.0

    pulse = (
        0.30 * _clamp(growth)
        + 0.25 * _clamp(profitability)
        + 0.25 * _clamp(debt_health)
        + 0.20 * _clamp(industry_edge)
    )
    return int(round(_clamp(pulse, 0.0, 100.0)))


@cached(ttl=120)
def calculate_metrics(ticker, *, include_sec=True, include_quarterly=True):
    """Calculates all financial metrics for a given ticker locally."""
    ticker = ticker.upper()
    snapshot = _snapshot_metrics(ticker)
    metrics = {
        "ticker": ticker,
        "price": None,
        "change": None,
        "pct_change": None,
        "market_cap": None,
        "volume": None,
        "pe_ratio": None,
        "ps_ratio": None,
        "enterprise_value": None,
        "profit_margin": None,
        "roe": None,
        "payout_ratio": None,
        "eps": None,
        "shares_outstanding": None,
        "assets": None,
        "liabilities": None,
        "equity": None,
        "sector": snapshot.get("sector") or "N/A",
        "industry": snapshot.get("industry") or "N/A",
        "beta": None,
        "dividend_yield": snapshot.get("dividend_yield"),
        "fifty_two_week_high": snapshot.get("fifty_two_week_high"),
        "fifty_two_week_low": snapshot.get("fifty_two_week_low"),
        "company_name": snapshot.get("company_name") or "N/A",
        "quarterly_revenue_growth": None,
        "quarterly_operating_expenses": None,
    }

    # --- Phase 1: Live price from Yahoo Finance ---
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d" if include_quarterly or include_sec else "2d")
        if not hist.empty and len(hist) >= 2:
            close = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2])
            change = close - prev
            pct_change = (change / prev) * 100

            metrics["price"] = round(close, 2)
            metrics["change"] = round(change, 2)
            metrics["pct_change"] = round(pct_change, 2)
            metrics["volume"] = int(hist["Volume"].iloc[-1])

        info = stock.info
        metrics["sector"] = info.get("sector") or metrics["sector"]
        metrics["industry"] = info.get("industry") or metrics["industry"]
        metrics["beta"] = info.get("beta")
        metrics["dividend_yield"] = info.get("dividendYield") or metrics["dividend_yield"]
        metrics["payout_ratio"] = info.get("payoutRatio")
        metrics["ps_ratio"] = info.get("priceToSalesTrailing12Months")
        metrics["enterprise_value"] = info.get("enterpriseValue")
        metrics["profit_margin"] = info.get("profitMargins")
        metrics["roe"] = info.get("returnOnEquity")
        metrics["fifty_two_week_high"] = info.get("fiftyTwoWeekHigh") or metrics["fifty_two_week_high"]
        metrics["fifty_two_week_low"] = info.get("fiftyTwoWeekLow") or metrics["fifty_two_week_low"]
        metrics["company_name"] = (
            info.get("shortName")
            or info.get("longName")
            or metrics["company_name"]
        )

        revenue_growth = _safe_float(info.get("revenueGrowth"))
        if revenue_growth is not None:
            # yfinance returns a ratio; the UI displays this field as a percent number.
            metrics["quarterly_revenue_growth"] = round(revenue_growth * 100.0, 2)

        # Fast fallback values. SEC-derived values below override these when available.
        market_cap = info.get("marketCap") or snapshot.get("market_cap")
        pe = info.get("trailingPE") or info.get("forwardPE") or snapshot.get("pe_ratio")
        if market_cap is not None:
            metrics["market_cap"] = float(market_cap)
        if pe is not None:
            metrics["pe_ratio"] = float(pe)

        if include_quarterly:
            # Grab quarterly income statement for growth metrics
            q_stmt = stock.quarterly_income_stmt
            if not q_stmt.empty:
                if "Total Revenue" in q_stmt.index:
                    revs = q_stmt.loc["Total Revenue"].dropna()
                    if len(revs) >= 2:
                        current_rev = float(revs.iloc[0])
                        prev_rev = float(revs.iloc[1])
                        if prev_rev and prev_rev != 0:
                            growth = ((current_rev - prev_rev) / abs(prev_rev)) * 100
                            metrics["quarterly_revenue_growth"] = round(growth, 2)

                if "Operating Expense" in q_stmt.index:
                    exp = q_stmt.loc["Operating Expense"].dropna()
                    if len(exp) >= 1:
                        metrics["quarterly_operating_expenses"] = float(exp.iloc[0])

    except Exception:
        pass

    # --- Phase 2: SEC Fundamentals ---
    if include_sec:
        cik = get_cik_for_ticker(ticker)
        if cik:
            facts = get_sec_facts(cik)
            if facts:
                eps = extract_latest_sec_fact(
                    facts, "EarningsPerShareDiluted", unit="USD/shares"
                )
                if eps is None:
                    eps = extract_latest_sec_fact(
                        facts, "EarningsPerShareBasic", unit="USD/shares"
                    )

                shares = extract_latest_sec_fact(
                    facts, "EntityCommonStockSharesOutstanding", unit="shares"
                )
                if shares is None:
                    shares = extract_latest_sec_fact(
                        facts, "CommonStockSharesOutstanding", unit="shares"
                    )

                assets = _first_sec_fact(
                    facts,
                    "Assets",
                    "AssetsCurrent",
                    unit="USD",
                )
                liabilities = _first_sec_fact(
                    facts,
                    "Liabilities",
                    "LiabilitiesCurrent",
                    unit="USD",
                )
                revenue = _first_sec_fact(
                    facts,
                    "Revenues",
                    "RevenueFromContractWithCustomerExcludingAssessedTax",
                    "SalesRevenueNet",
                    unit="USD",
                )
                net_income = _first_sec_fact(
                    facts,
                    "NetIncomeLoss",
                    "ProfitLoss",
                    unit="USD",
                )
                equity = _first_sec_fact(
                    facts,
                    "StockholdersEquity",
                    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
                    unit="USD",
                )

                metrics["eps"] = eps
                metrics["shares_outstanding"] = shares
                metrics["assets"] = assets
                metrics["liabilities"] = liabilities

                if assets and liabilities:
                    metrics["equity"] = assets - liabilities
                elif equity is not None:
                    metrics["equity"] = equity

                if metrics["profit_margin"] is None and revenue and net_income is not None:
                    try:
                        if float(revenue) != 0:
                            metrics["profit_margin"] = float(net_income) / float(revenue)
                    except (TypeError, ValueError):
                        pass

                # --- Phase 3: Derived calculations ---
                if metrics["price"] is not None:
                    if eps and eps > 0:
                        metrics["pe_ratio"] = round(metrics["price"] / eps, 2)
                    if shares and shares > 0:
                        metrics["market_cap"] = round(metrics["price"] * shares, 0)

    if snapshot.get("radar_pulse") is not None:
        metrics["radar_pulse"] = int(snapshot["radar_pulse"])
    else:
        metrics["radar_pulse"] = compute_radar_pulse(metrics)
        _persist_radar_pulse_if_missing(ticker, metrics["radar_pulse"])
    return metrics


@cached(ttl=120)
def get_historical_data(ticker, period="1y", interval="1d"):
    """Fetches OHLCV historical data and returns it as a list of dicts."""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        if df.empty:
            return []
        df = df.reset_index()
        # yfinance uses "Date" for daily/weekly data and "Datetime" for intraday.
        date_col = "Date" if "Date" in df.columns else "Datetime" if "Datetime" in df.columns else df.columns[0]
        df = df.rename(columns={date_col: "Date"})
        df["Date"] = df["Date"].astype(str)
        records = df[["Date", "Open", "High", "Low", "Close", "Volume"]].to_dict("records")
        for r in records:
            for k in ["Open", "High", "Low", "Close"]:
                r[k] = round(r[k], 2)
        return records
    except Exception:
        return []


@cached(ttl=120)
def get_sparkline_data(ticker):
    """Returns last 30 days of closing prices for a sparkline chart."""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="1mo", interval="1d")
        if df.empty:
            return []
        return [round(float(p), 2) for p in df["Close"].tolist()]
    except Exception:
        return []


@cached(ttl=300)
def get_movers():
    """Calculates top gainers and losers from a set of popular tickers."""
    scan_list = [
        "AAPL", "MSFT", "NVDA", "TSLA", "AMD", "GOOGL", "AMZN", "META",
        "NFLX", "JPM", "V", "WMT", "DIS", "INTC", "BA", "PYPL",
        "CRM", "UBER", "COIN", "PLTR",
    ]
    data = []
    for t in scan_list:
        try:
            stock = yf.Ticker(t)
            hist = stock.history(period="2d")
            if len(hist) >= 2:
                close = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2])
                pct = ((close - prev) / prev) * 100
                vol = int(hist["Volume"].iloc[-1])
                data.append({
                    "ticker": t,
                    "price": round(close, 2),
                    "change": round(close - prev, 2),
                    "pct_change": round(pct, 2),
                    "volume": vol,
                })
        except Exception:
            continue

    sorted_data = sorted(data, key=lambda x: x["pct_change"], reverse=True)
    gainers = [d for d in sorted_data if d["pct_change"] > 0][:5]
    losers = [d for d in sorted_data if d["pct_change"] < 0][-5:]
    losers.sort(key=lambda x: x["pct_change"])

    return {"gainers": gainers, "losers": losers}


@cached(ttl=120)
def get_indices():
    """Returns current values for major market indices."""
    indices = {
        "^GSPC": "S&P 500",
        "^DJI": "Dow Jones",
        "^IXIC": "NASDAQ",
        "^RUT": "Russell 2000",
    }
    result = []
    for symbol, name in indices.items():
        try:
            stock = yf.Ticker(symbol)
            hist = stock.history(period="5d")
            if len(hist) >= 2:
                close = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2])
                change = close - prev
                pct = (change / prev) * 100
                result.append({
                    "symbol": symbol,
                    "name": name,
                    "price": round(close, 2),
                    "change": round(change, 2),
                    "pct_change": round(pct, 2),
                })
        except Exception:
            continue
    return result


@cached(ttl=120)
def get_markets_snapshot():
    """Returns a snapshot across futures, global indices, ETFs, and crypto."""
    instruments = [
        # Futures (Yahoo symbols)
        {"symbol": "ES=F", "name": "S&P 500 Futures", "group": "Futures"},
        {"symbol": "NQ=F", "name": "Nasdaq 100 Futures", "group": "Futures"},
        {"symbol": "YM=F", "name": "Dow Futures", "group": "Futures"},
        {"symbol": "RTY=F", "name": "Russell 2000 Futures", "group": "Futures"},
        {"symbol": "CL=F", "name": "Crude Oil", "group": "Futures"},
        {"symbol": "GC=F", "name": "Gold", "group": "Futures"},
        # ETFs / Benchmarks
        {"symbol": "SPY", "name": "SPDR S&P 500", "group": "ETFs"},
        # Global Indices
        {"symbol": "^NSEI", "name": "Nifty 50", "group": "Global"},
        {"symbol": "^N225", "name": "Nikkei 225", "group": "Global"},
        {"symbol": "000001.SS", "name": "SSE Composite", "group": "Global"},
        {"symbol": "^HSI", "name": "Hang Seng", "group": "Global"},
        # Crypto
        {"symbol": "BTC-USD", "name": "Bitcoin", "group": "Crypto"},
        {"symbol": "ETH-USD", "name": "Ethereum", "group": "Crypto"},
        {"symbol": "SOL-USD", "name": "Solana", "group": "Crypto"},
    ]

    result = []
    for inst in instruments:
        symbol = inst["symbol"]
        try:
            stock = yf.Ticker(symbol)
            hist = stock.history(period="5d")
            if len(hist) >= 2:
                close = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2])
                if prev == 0:
                    continue
                change = close - prev
                pct = (change / prev) * 100
                result.append(
                    {
                        "symbol": symbol,
                        "name": inst["name"],
                        "group": inst["group"],
                        "price": round(close, 2),
                        "change": round(change, 2),
                        "pct_change": round(pct, 2),
                    }
                )
        except Exception:
            continue

    return result

@cached(ttl=300)
def get_sector_performance():
    """Returns top performing sectors from the movers scan list."""
    scan_list = [
        "AAPL", "MSFT", "NVDA", "TSLA", "AMD", "GOOGL", "AMZN", "META",
        "NFLX", "JPM", "V", "WMT", "DIS", "INTC", "BA", "PYPL",
        "CRM", "UBER", "COIN", "PLTR",
    ]

    sectors = {}
    for t in scan_list:
        try:
            stock = yf.Ticker(t)
            hist = stock.history(period="2d")
            if len(hist) < 2:
                continue

            close = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2])
            if prev == 0:
                continue
            pct = ((close - prev) / prev) * 100

            info = stock.info or {}
            sector = info.get("sector") or "Other"

            sectors.setdefault(sector, []).append(float(pct))
        except Exception:
            continue

    perf = []
    for sector, pct_changes in sectors.items():
        if not pct_changes:
            continue
        avg = sum(pct_changes) / len(pct_changes)
        perf.append(
            {
                "sector": sector,
                "avg_pct_change": round(avg, 2),
                "count": len(pct_changes),
            }
        )

    perf.sort(key=lambda x: x["avg_pct_change"], reverse=True)
    return {"top": perf[:2]}


@cached(ttl=300)
def get_news(ticker):
    """Fetches recent news for a ticker via yfinance."""
    try:
        stock = yf.Ticker(ticker)
        news = stock.news[:8]
        return [
            {
                "title": n.get("title", ""),
                "link": n.get("link", ""),
                "publisher": n.get("publisher", ""),
                "published": n.get("providerPublishTime", 0),
            }
            for n in news
        ]
    except Exception:
        return []
