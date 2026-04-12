"""Local financial metric calculation engine.

Combines live price data from yfinance with fundamental data
from SEC EDGAR to calculate metrics without any paid API keys.
"""

import time

import yfinance as yf
import pandas as pd
import concurrent.futures
from sec_engine import get_cik_for_ticker, get_sec_facts, extract_latest_sec_fact
from sec_engine import get_sec_tickers_list
from sec_engine import get_sp500_constituents
from cache import cached

# Yahoo ties requests to one session/crumb; bursty parallel calls often return 401 / Invalid Crumb.
yf.config.network.retries = 3


def _clamp(n, lo=0.0, hi=100.0):
    return max(lo, min(hi, n))


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
    metrics = {
        "ticker": ticker.upper(),
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
        "sector": "N/A",
        "industry": "N/A",
        "beta": None,
        "dividend_yield": None,
        "fifty_two_week_high": None,
        "fifty_two_week_low": None,
        "company_name": "N/A",
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
        metrics["sector"] = info.get("sector", "N/A")
        metrics["industry"] = info.get("industry", "N/A")
        metrics["beta"] = info.get("beta")
        metrics["dividend_yield"] = info.get("dividendYield")
        metrics["payout_ratio"] = info.get("payoutRatio")
        metrics["ps_ratio"] = info.get("priceToSalesTrailing12Months")
        metrics["enterprise_value"] = info.get("enterpriseValue")
        metrics["profit_margin"] = info.get("profitMargins")
        metrics["roe"] = info.get("returnOnEquity")
        metrics["fifty_two_week_high"] = info.get("fiftyTwoWeekHigh")
        metrics["fifty_two_week_low"] = info.get("fiftyTwoWeekLow")
        metrics["company_name"] = info.get("shortName", info.get("longName", "N/A"))

        if not include_sec:
            # Fast-path derived values from yfinance info (avoids SEC calls).
            market_cap = info.get("marketCap")
            pe = info.get("trailingPE") or info.get("forwardPE")
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

                assets = extract_latest_sec_fact(facts, "Assets", unit="USD")
                liabilities = extract_latest_sec_fact(facts, "Liabilities", unit="USD")

                metrics["eps"] = eps
                metrics["shares_outstanding"] = shares
                metrics["assets"] = assets
                metrics["liabilities"] = liabilities

                if assets and liabilities:
                    metrics["equity"] = assets - liabilities

                # --- Phase 3: Derived calculations ---
                if metrics["price"] is not None:
                    if eps and eps > 0:
                        metrics["pe_ratio"] = round(metrics["price"] / eps, 2)
                    if shares and shares > 0:
                        metrics["market_cap"] = round(metrics["price"] * shares, 0)

    metrics["radar_pulse"] = compute_radar_pulse(metrics)
    return metrics


@cached(ttl=120)
def get_screener_results(
    *,
    tickers,
    market_cap_min=None,
    market_cap_max=None,
    pe_min=None,
    pe_max=None,
    volume_min=None,
    volume_max=None,
    price_min=None,
    price_max=None,
    sector=None,
    dividends_only=False,
    eval_limit=None,
    limit=250,
    meta_source=None,
):
    """Returns a list of quote-like rows for a screener table.

    Notes:
    - Uses calculate_metrics() per ticker (cached).
    - Intentionally bounded by a universe list (tickers param) to keep latency reasonable.
    """
    # This endpoint is a hot path. We batch price/volume via yfinance download and
    # enrich a bounded candidate set with cached yfinance info (parallelized) so
    # filters like Market Cap / P/E actually work without scanning the entire market.

    return_limit = max(0, int(limit))
    tickers = list(tickers)
    if eval_limit is not None:
        tickers = tickers[: max(0, int(eval_limit))]
    if not tickers:
        return []

    rows = []

    def ok_range(v, min_v, max_v):
        if v is None:
            return True  # treat missing as "pass" for screener snapshot
        if min_v is not None and v < min_v:
            return False
        if max_v is not None and v > max_v:
            return False
        return True

    # The UI sliders use fixed maxima (e.g., "80+" for P/E). When a user drags to the max,
    # we treat that as "no upper bound" (same for 0 on the min side).
    UI_MAX_MARKET_CAP = 2_000_000_000_000
    UI_MAX_PE = 80
    UI_MAX_VOLUME = 100_000_000
    UI_MAX_PRICE = 600

    def normalize_range(min_v, max_v, ui_max):
        if min_v is not None and min_v <= 0:
            min_v = None
        if max_v is not None and max_v >= ui_max:
            max_v = None
        return min_v, max_v

    market_cap_min, market_cap_max = normalize_range(
        market_cap_min, market_cap_max, UI_MAX_MARKET_CAP
    )
    pe_min, pe_max = normalize_range(pe_min, pe_max, UI_MAX_PE)
    volume_min, volume_max = normalize_range(volume_min, volume_max, UI_MAX_VOLUME)
    price_min, price_max = normalize_range(price_min, price_max, UI_MAX_PRICE)

    meta_source = (meta_source or "").strip().lower()

    # Map ticker -> metadata (name/sector/industry) from the chosen universe source.
    if meta_source == "sp500":
        try:
            constituents = get_sp500_constituents()
            name_map = {c["ticker"]: (c.get("company_name") or c["ticker"]) for c in constituents}
            sector_map = {c["ticker"]: (c.get("sector") or "N/A") for c in constituents}
            industry_map = {c["ticker"]: (c.get("industry") or "N/A") for c in constituents}
        except Exception:
            name_map = {}
            sector_map = {}
            industry_map = {}
    else:
        name_map = {}
        try:
            sec_list = get_sec_tickers_list()
            name_map = {x["ticker"]: x.get("name", "") for x in sec_list}
        except Exception:
            name_map = {}
        sector_map = {}
        industry_map = {}

    def _chunks(items, size):
        for i in range(0, len(items), size):
            yield items[i : i + size]

    def _download_snapshot(chunk):
        try:
            df = yf.download(
                " ".join(chunk),
                period="5d",
                group_by="ticker",
                threads=False,
                progress=False,
            )
        except Exception:
            return {}

        if df is None or getattr(df, "empty", True):
            return {}

        multi = getattr(df.columns, "nlevels", 1) > 1
        out = {}
        for t in chunk:
            try:
                if multi:
                    if t not in df.columns.get_level_values(0):
                        continue
                    sub = df[t]
                else:
                    sub = df
                if sub is None or sub.empty:
                    continue

                closes = sub["Close"].dropna() if "Close" in sub.columns else None
                if closes is None or closes.empty:
                    continue
                close = float(closes.iloc[-1])
                prev = float(closes.iloc[-2]) if len(closes) >= 2 else close
                if prev == 0:
                    prev = close
                vol = int(sub["Volume"].iloc[-1]) if "Volume" in sub.columns else None
                out[t] = (close, prev, vol)
            except Exception:
                continue
        return out

    # First pass: build candidates from OHLCV snapshot (fast).
    snapshots = {}
    # Chunk + serialize downloads (threads=False) so we do not invalidate Yahoo's shared crumb.
    for chunk in _chunks(tickers, 50):
        snapshots.update(_download_snapshot(chunk))
        time.sleep(0.15)

    # Retry missing symbols with smaller batches (yfinance can intermittently drop some tickers in large calls).
    missing = [t for t in tickers if t not in snapshots]
    if missing:
        for chunk in _chunks(missing, 12):
            snapshots.update(_download_snapshot(chunk))
            time.sleep(0.15)

    candidates = []
    for t in tickers:
        try:
            if t not in snapshots:
                continue

            close, prev, vol = snapshots[t]
            pct = ((close - prev) / prev) * 100.0

            if volume_min is not None or volume_max is not None:
                if not ok_range(vol, volume_min, volume_max):
                    continue

            if price_min is not None or price_max is not None:
                if not ok_range(close, price_min, price_max):
                    continue

            candidates.append(
                {
                    "ticker": t,
                    "company_name": name_map.get(t) or t,
                    "price": round(close, 2),
                    "pct_change": round(pct, 2),
                    "volume": vol,
                    "market_cap": None,
                    "pe_ratio": None,
                    "sector": sector_map.get(t) or "N/A",
                    "industry": industry_map.get(t) or "N/A",
                    "dividend_yield": None,
                    "fifty_two_week_high": None,
                    "fifty_two_week_low": None,
                    "radar_pulse": None,
                }
            )
        except Exception:
            continue

    if not candidates:
        return []

    # Second pass: only enrich fundamentals if the filter bounds are actually restrictive.
    # The UI uses fixed "max" values (e.g., P/E 80+) which should behave like "no upper bound".
    market_cap_filter_active = (
        (market_cap_min is not None)
        or (market_cap_max is not None)
    )
    pe_filter_active = (
        (pe_min is not None)
        or (pe_max is not None)
    )

    # Apply sector filter using universe metadata when available (fast).
    if sector and sector != "All":
        candidates = [c for c in candidates if (c.get("sector") or "N/A") == sector]
        if not candidates:
            return []

    # No expensive filters => return the snapshot rows immediately.
    if not market_cap_filter_active and not pe_filter_active and not dividends_only:
        return candidates[:return_limit]

    @cached(ttl=900)
    def _yf_fast_market_cap(ticker):
        try:
            stock = yf.Ticker(ticker)
            fast = getattr(stock, "fast_info", None) or {}
            v = fast.get("marketCap")
            return float(v) if v is not None else None
        except Exception:
            return None

    @cached(ttl=900)
    def _yf_info_subset(ticker):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info or {}
            return {
                "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
                "sector": info.get("sector") or "N/A",
                "industry": info.get("industry") or "N/A",
                "dividend_yield": info.get("dividendYield"),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            }
        except Exception:
            return {
                "pe_ratio": None,
                "sector": "N/A",
                "industry": "N/A",
                "dividend_yield": None,
                "fifty_two_week_high": None,
                "fifty_two_week_low": None,
            }

    # Enrichment can get expensive at S&P 500 scale. Process candidates in batches
    # until we fill `return_limit`, rather than pulling `.info` for every ticker.
    candidates.sort(key=lambda r: (r.get("pct_change") is None, -(r.get("pct_change") or 0.0)))

    max_workers = 4
    batch_size = 60
    # Hard cap to keep the endpoint responsive on low-tier hosting.
    max_scan = min(len(candidates), max(return_limit * 2, 240), 420)

    results = []
    cursor = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        while cursor < len(candidates) and cursor < max_scan and len(results) < return_limit:
            batch = [dict(x) for x in candidates[cursor : cursor + batch_size]]
            cursor += batch_size

            if market_cap_filter_active:
                caps = list(ex.map(_yf_fast_market_cap, [c["ticker"] for c in batch]))
                for c, cap in zip(batch, caps):
                    c["market_cap"] = cap
                batch = [
                    c
                    for c in batch
                    if ok_range(c.get("market_cap"), market_cap_min, market_cap_max)
                ]
                if not batch:
                    continue

            if pe_filter_active or dividends_only:
                infos = list(ex.map(_yf_info_subset, [c["ticker"] for c in batch]))
                enriched = []
                for c, info in zip(batch, infos):
                    c.update(info)
                    enriched.append(c)

                batch = []
                for c in enriched:
                    if pe_filter_active and not ok_range(c.get("pe_ratio"), pe_min, pe_max):
                        continue
                    if dividends_only and (c.get("dividend_yield") or 0) <= 0:
                        continue
                    batch.append(c)

                if not batch:
                    continue

            results.extend(batch)

    return results[:return_limit]

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
