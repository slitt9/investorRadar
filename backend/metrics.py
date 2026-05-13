"""Local financial metric calculation engine.

Combines live price data from yfinance with fundamental data
from SEC EDGAR to calculate metrics without any paid API keys.
"""

import math

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
                    radar_pulse, ps_ratio, enterprise_value, roe, profit_margin,
                    quarterly_revenue_growth, assets, liabilities, equity, beta
                FROM stock_snapshot
                WHERE ticker = ?
                """,
                (ticker.upper(),),
            ).fetchone()
            return dict(row) if row else {}
    except Exception:
        return {}


def _persist_radar_pulse(ticker, radar_pulse):
    """Always persist the latest computed pulse (single source of truth on refresh)."""
    if radar_pulse is None:
        return
    try:
        with get_db() as conn:
            conn.execute(
                """
                UPDATE stock_snapshot
                SET radar_pulse = ?
                WHERE ticker = ?
                """,
                (int(radar_pulse), ticker.upper()),
            )
    except Exception:
        pass


def _score_forward_revenue_growth(growth_pct: float | None) -> float:
    """Map forward / trailing revenue growth (percent points) to 0..100 (G)."""
    if growth_pct is None or math.isnan(growth_pct):
        return 50.0
    if growth_pct <= -10:
        return 0.0
    if growth_pct <= 0:
        return (growth_pct + 10) * 4.0
    if growth_pct <= 20:
        return 40.0 + (growth_pct / 20.0) * 40.0
    return 80.0 + _clamp((growth_pct - 20) / 30.0 * 20.0, 0.0, 20.0)


def _score_fcf_margin(fcf_margin: float | None) -> float:
    """FCF / revenue as a fraction (P). ~18% FCF margin maps to ~100."""
    if fcf_margin is None or math.isnan(fcf_margin):
        return 50.0
    if fcf_margin <= 0:
        return 0.0
    return _clamp((fcf_margin / 0.18) * 100.0, 0.0, 100.0)


def _score_interest_coverage(coverage: float | None) -> float:
    """Interest coverage = EBIT-like / interest (D)."""
    if coverage is None or math.isnan(coverage):
        return 50.0
    if coverage <= 0:
        return 0.0
    if coverage >= 15:
        return 100.0
    return _clamp(coverage / 15.0 * 100.0, 0.0, 100.0)


def _score_inverse_peg(peg: float | None) -> float:
    """Lower PEG -> higher score (V). Neutral when unknown."""
    if peg is None or math.isnan(peg) or peg <= 0:
        return 50.0
    return _clamp((2.5 - min(peg, 2.5)) / 2.5 * 100.0, 0.0, 100.0)


def _rsi_14(closes: list[float]) -> float | None:
    if len(closes) < 15:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    window = deltas[-14:]
    gains = [max(d, 0.0) for d in window]
    losses = [max(-d, 0.0) for d in window]
    ag = sum(gains) / 14.0
    al = sum(losses) / 14.0
    if al == 0:
        return 100.0 if ag > 0 else 50.0
    rs = ag / al
    return 100.0 - (100.0 / (1.0 + rs))


def _trend_3m_score(closes: list[float]) -> float | None:
    if len(closes) < 64:
        return None
    cur, old = closes[-1], closes[-64]
    if old <= 0:
        return None
    pct = (cur - old) / old * 100.0
    return _clamp((pct + 15.0) / 30.0 * 100.0, 0.0, 100.0)


def _forward_revenue_growth_pct(stock, info: dict, fallback_pct: float | None) -> float | None:
    """Prefer analyst forward revenue (+1y) when available; else Yahoo growth proxies."""
    if stock is not None:
        try:
            ge = getattr(stock, "growth_estimates", None)
            if ge is not None and not getattr(ge, "empty", True):
                if hasattr(ge, "index") and "Revenue" in ge.index:
                    row = ge.loc["Revenue"]
                    best = None
                    for col in row.index:
                        cs = str(col).upper()
                        if any(x in cs for x in ("+1", "1Y", "/1")):
                            v = _safe_float(row[col])
                            if v is not None and not math.isnan(v):
                                best = v if best is None else max(best, v)
                    if best is not None:
                        if abs(best) < 1.0:
                            best *= 100.0
                        return float(best)
        except Exception:
            pass
    eg = _safe_float(info.get("earningsGrowth"))
    if eg is not None:
        return eg * 100.0
    rg = _safe_float(info.get("revenueGrowth"))
    if rg is not None:
        return rg * 100.0
    return fallback_pct


def _fcf_margin(info: dict, facts, revenue_sec: float | None) -> float | None:
    fcf = _safe_float(info.get("freeCashflow"))
    rev = _safe_float(info.get("totalRevenue"))
    if fcf is not None and rev and rev != 0:
        return fcf / rev
    if not facts:
        return None
    ocf = _first_sec_fact(
        facts,
        "NetCashProvidedByUsedInOperatingActivities",
        unit="USD",
    )
    capex = _first_sec_fact(
        facts,
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "CapitalExpenditures",
        unit="USD",
    )
    rev = revenue_sec
    if rev is None or float(rev) == 0:
        rev = _first_sec_fact(
            facts,
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "SalesRevenueNet",
            unit="USD",
        )
    if ocf is None or rev is None or float(rev) == 0:
        return None
    try:
        capex_amt = float(capex) if capex is not None else 0.0
        fcf_est = float(ocf) - abs(capex_amt)
        return fcf_est / float(rev)
    except (TypeError, ValueError):
        return None


def _interest_coverage_raw(facts) -> float | None:
    if not facts:
        return None
    op = _first_sec_fact(facts, "OperatingIncomeLoss", unit="USD")
    interest = _first_sec_fact(
        facts,
        "InterestExpense",
        "InterestAndDebtExpense",
        unit="USD",
    )
    if op is None:
        return None
    op_f = float(op)
    if interest is None or abs(float(interest)) < 1e-9:
        return 100.0 if op_f > 0 else 0.0
    return op_f / abs(float(interest))


def _peg_ratio(info: dict, pe: float | None) -> float | None:
    direct = _safe_float(info.get("pegRatio"))
    if direct is not None and direct > 0:
        return direct
    if pe is None or pe <= 0:
        return None
    eg = _safe_float(info.get("earningsGrowth"))
    if eg is None or eg <= 0:
        return None
    g_pct = eg * 100.0
    if g_pct <= 0.01:
        return None
    return pe / g_pct


def _sector_profit_margin_percentile(
    conn, ticker: str, sector: str, current_pm: float | None
) -> float:
    if current_pm is None or not sector or str(sector).strip().upper() in ("", "N/A"):
        return 50.0
    key = str(sector).strip()
    rows = conn.execute(
        """
        SELECT profit_margin FROM stock_snapshot
        WHERE UPPER(ticker) != UPPER(?)
          AND TRIM(COALESCE(NULLIF(NULLIF(sector, 'N/A'), ''), '')) = ?
          AND profit_margin IS NOT NULL
        """,
        (ticker, key),
    ).fetchall()
    vals = []
    for (v,) in rows:
        try:
            fv = float(v)
            if not math.isnan(fv):
                vals.append(fv)
        except (TypeError, ValueError):
            continue
    if len(vals) < 5:
        return 50.0
    below = sum(1 for x in vals if x < current_pm)
    equal = sum(1 for x in vals if x == current_pm)
    return 100.0 * (below + 0.5 * equal) / len(vals)


def _momentum_score_from_history(stock) -> float | None:
    if stock is None:
        return None
    try:
        hist = stock.history(period="8mo", interval="1d")
        if hist is None or hist.empty or "Close" not in hist.columns:
            return None
        closes = [float(x) for x in hist["Close"].tolist() if x == x]
        if len(closes) < 20:
            return None
        rsi = _rsi_14(closes)
        tr = _trend_3m_score(closes)
        if rsi is not None and tr is not None:
            return _clamp(0.45 * rsi + 0.55 * tr, 0.0, 100.0)
        if rsi is not None:
            return _clamp(rsi, 0.0, 100.0)
        if tr is not None:
            return _clamp(tr, 0.0, 100.0)
    except Exception:
        return None
    return None


def build_radar_pulse_inputs(
    ticker: str,
    metrics: dict,
    *,
    stock,
    info: dict,
    facts,
    include_momentum: bool = True,
    revenue_sec: float | None = None,
) -> dict:
    """Assemble raw inputs for :func:`compute_radar_pulse` (G,P,D,I,V,M)."""
    ticker = ticker.upper()
    info = info or {}
    sector = (metrics.get("sector") or "").strip() or "N/A"
    pe = _safe_float(metrics.get("pe_ratio"))
    pm = _safe_float(metrics.get("profit_margin"))
    qrev = _safe_float(metrics.get("quarterly_revenue_growth"))

    fwd_g = _forward_revenue_growth_pct(stock, info, qrev)
    fcf_m = _fcf_margin(info, facts, revenue_sec)
    cov = _interest_coverage_raw(facts)
    peg = _peg_ratio(info, pe)

    mom = None
    if include_momentum:
        mom = _momentum_score_from_history(stock)

    sector_pct = 50.0
    try:
        with get_db() as conn:
            sector_pct = _sector_profit_margin_percentile(conn, ticker, sector, pm)
    except Exception:
        sector_pct = 50.0

    return {
        "forward_revenue_growth_pct": fwd_g,
        "fcf_margin": fcf_m,
        "interest_coverage": cov,
        "sector_percentile": sector_pct,
        "peg": peg,
        "momentum_score": mom,
    }


def compute_radar_pulse(pulse: dict) -> int:
    """Radar Stock Pulse (0-100), six-factor model.

    Pulse = round(clamp(0.25*G + 0.20*P + 0.15*D + 0.15*I + 0.15*V + 0.10*M))

    G — Forward / analyst-skewed revenue growth (%), scaled 0..100
    P — FCF margin (free cash flow / revenue), scaled 0..100
    D — Interest coverage (EBIT-like / interest), scaled 0..100
    I — Profit-margin percentile within the same sector (0..100)
    V — Inverse PEG (Yahoo pegRatio or P/E ÷ earnings growth %)
    M — RSI + 3-month price trend blend (0..100); optional (neutral 50 when omitted)
    """
    g_raw = pulse.get("forward_revenue_growth_pct")
    try:
        g_pct = float(g_raw) if g_raw is not None else None
        if g_pct is not None and math.isnan(g_pct):
            g_pct = None
    except (TypeError, ValueError):
        g_pct = None
    G = _score_forward_revenue_growth(g_pct)
    P = _score_fcf_margin(_safe_float(pulse.get("fcf_margin")))
    cov_raw = pulse.get("interest_coverage")
    try:
        cov = float(cov_raw) if cov_raw is not None else None
        if cov is not None and math.isnan(cov):
            cov = None
    except (TypeError, ValueError):
        cov = None
    D = _score_interest_coverage(cov)
    I_raw = pulse.get("sector_percentile")
    try:
        I = float(I_raw) if I_raw is not None else 50.0
        if math.isnan(I):
            I = 50.0
    except (TypeError, ValueError):
        I = 50.0
    V = _score_inverse_peg(_safe_float(pulse.get("peg")))
    M_raw = pulse.get("momentum_score")
    try:
        M = float(M_raw) if M_raw is not None else 50.0
        if math.isnan(M):
            M = 50.0
    except (TypeError, ValueError):
        M = 50.0

    pulse_val = (
        0.25 * _clamp(G)
        + 0.20 * _clamp(P)
        + 0.15 * _clamp(D)
        + 0.15 * _clamp(I)
        + 0.15 * _clamp(V)
        + 0.10 * _clamp(M)
    )
    return int(round(_clamp(pulse_val, 0.0, 100.0)))


@cached(ttl=120)
def calculate_metrics(ticker, *, include_sec=True, include_quarterly=True):
    """Calculates all financial metrics for a given ticker locally."""
    ticker = ticker.upper()
    snapshot = _snapshot_metrics(ticker)

    def _snap(name):
        value = snapshot.get(name)
        if value in (None, "", "N/A"):
            return None
        return value

    metrics = {
        "ticker": ticker,
        "price": None,
        "change": None,
        "pct_change": None,
        "market_cap": _snap("market_cap"),
        "volume": None,
        "pe_ratio": _snap("pe_ratio"),
        "ps_ratio": _snap("ps_ratio"),
        "enterprise_value": _snap("enterprise_value"),
        "profit_margin": _snap("profit_margin"),
        "roe": _snap("roe"),
        "payout_ratio": None,
        "eps": None,
        "shares_outstanding": None,
        "assets": _snap("assets"),
        "liabilities": _snap("liabilities"),
        "equity": _snap("equity"),
        "sector": snapshot.get("sector") or "N/A",
        "industry": snapshot.get("industry") or "N/A",
        "beta": _snap("beta"),
        "dividend_yield": _snap("dividend_yield"),
        "fifty_two_week_high": _snap("fifty_two_week_high"),
        "fifty_two_week_low": _snap("fifty_two_week_low"),
        "company_name": snapshot.get("company_name") or "N/A",
        "quarterly_revenue_growth": _snap("quarterly_revenue_growth"),
        "quarterly_operating_expenses": None,
    }

    # --- Phase 1: Live price from Yahoo Finance ---
    stock = None
    info: dict = {}
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

        info = dict(stock.info or {})

        def _overlay(key, value):
            value = _safe_float(value) if isinstance(value, (int, float)) else value
            if value not in (None, "", "N/A"):
                metrics[key] = value

        _overlay("sector", info.get("sector"))
        _overlay("industry", info.get("industry"))
        _overlay("beta", _safe_float(info.get("beta")))
        _overlay("dividend_yield", _safe_float(info.get("dividendYield")))
        _overlay("payout_ratio", _safe_float(info.get("payoutRatio")))
        _overlay("ps_ratio", _safe_float(info.get("priceToSalesTrailing12Months")))
        _overlay("enterprise_value", _safe_float(info.get("enterpriseValue")))
        _overlay("profit_margin", _safe_float(info.get("profitMargins")))
        _overlay("roe", _safe_float(info.get("returnOnEquity")))
        _overlay("fifty_two_week_high", _safe_float(info.get("fiftyTwoWeekHigh")))
        _overlay("fifty_two_week_low", _safe_float(info.get("fiftyTwoWeekLow")))
        company_name = info.get("shortName") or info.get("longName")
        if company_name:
            metrics["company_name"] = company_name

        revenue_growth = _safe_float(info.get("revenueGrowth"))
        if revenue_growth is not None:
            # yfinance returns a ratio; the UI displays this field as a percent number.
            metrics["quarterly_revenue_growth"] = round(revenue_growth * 100.0, 2)

        # Fast fallback values. SEC-derived values below override these when available.
        live_cap = _safe_float(info.get("marketCap"))
        if live_cap is not None:
            metrics["market_cap"] = live_cap
        live_pe = _safe_float(info.get("trailingPE")) or _safe_float(info.get("forwardPE"))
        if live_pe is not None and live_pe > 0:
            metrics["pe_ratio"] = live_pe

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
    sec_facts = None
    rev_for_pulse = None
    if include_sec:
        cik = get_cik_for_ticker(ticker)
        if cik:
            facts = get_sec_facts(cik)
            if facts:
                sec_facts = facts
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
                rev_for_pulse = revenue
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

                if eps is not None:
                    metrics["eps"] = eps
                if shares is not None:
                    metrics["shares_outstanding"] = shares
                if assets is not None:
                    metrics["assets"] = assets
                if liabilities is not None:
                    metrics["liabilities"] = liabilities

                if assets is not None and liabilities is not None:
                    metrics["equity"] = assets - liabilities
                elif equity is not None and metrics["equity"] is None:
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

    pl_stock = stock
    pl_info = info
    if pl_stock is None:
        try:
            pl_stock = yf.Ticker(ticker)
            pl_info = dict(pl_stock.info or {})
        except Exception:
            pl_stock = None
            pl_info = {}

    pulse_inputs = build_radar_pulse_inputs(
        ticker,
        metrics,
        stock=pl_stock,
        info=pl_info,
        facts=sec_facts,
        include_momentum=True,
        revenue_sec=_safe_float(rev_for_pulse) if rev_for_pulse is not None else None,
    )
    metrics["radar_pulse"] = compute_radar_pulse(pulse_inputs)
    _persist_radar_pulse(ticker, metrics["radar_pulse"])
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
