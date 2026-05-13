"""Enrich stock_snapshot with SEC-derived fundamentals + cached Yahoo metadata."""

from __future__ import annotations

import argparse
import gc
import os
import time
from datetime import datetime, timezone

import yfinance as yf

from db import ensure_schema, get_db
from metrics import build_radar_pulse_inputs, compute_radar_pulse
from sec_engine import (
    extract_latest_sec_fact,
    get_cik_for_ticker,
    get_sec_facts,
    get_sp500_constituents,
    normalize_sector,
)
from universe_config import MAG7_TICKERS, MEGA_CAP_TICKERS, POPULAR_TICKERS
from universe_sync import get_searchable_equity_tickers

yf.config.network.retries = 3


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve_tickers(mode: str) -> list[str]:
    mode = mode.strip().lower()
    if mode == "mag7":
        return list(MAG7_TICKERS)
    if mode == "sp500":
        cons = get_sp500_constituents()
        return [c["ticker"] for c in cons] if cons else []
    if mode == "mega":
        cons = get_sp500_constituents()
        mega = set(MEGA_CAP_TICKERS)
        if cons:
            return [c["ticker"] for c in cons if c.get("ticker") in mega]
        return sorted(mega)
    if mode == "popular":
        return list(POPULAR_TICKERS)
    if mode in ("all", "equities", "extended"):
        cap = int(os.environ.get("REFRESH_ALL_CAP", "2500"))
        return get_searchable_equity_tickers(limit=cap)
    raise ValueError(f"Unknown universe mode: {mode}")


def _safe_float(value) -> float | None:
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


def refresh_fundamentals(
    tickers: list[str],
    *,
    yahoo_delay_s: float = 0.35,
) -> dict:
    ensure_schema()
    sp500 = get_sp500_constituents() or []
    sp500_meta = {c["ticker"]: c for c in sp500}
    meta_ts = _utc_now_iso()
    tickers = [t.upper().strip() for t in tickers if t and str(t).strip()]

    updated = 0
    skipped = 0

    update_sql = """
        UPDATE stock_snapshot SET
            market_cap = ?,
            pe_ratio = ?,
            sector = ?,
            industry = ?,
            dividend_yield = ?,
            fifty_two_week_high = ?,
            fifty_two_week_low = ?,
            radar_pulse = ?,
            company_name = COALESCE(?, company_name),
            ps_ratio = ?,
            enterprise_value = ?,
            roe = ?,
            profit_margin = ?,
            quarterly_revenue_growth = ?,
            assets = ?,
            liabilities = ?,
            equity = ?,
            beta = ?
        WHERE ticker = ?
    """

    with get_db() as conn:
        for processed, ticker in enumerate(tickers, 1):
            row = conn.execute(
                "SELECT price, company_name FROM stock_snapshot WHERE ticker = ?",
                (ticker,),
            ).fetchone()
            if not row or row["price"] is None:
                skipped += 1
                continue

            price = float(row["price"])
            company_name = row["company_name"]

            meta = sp500_meta.get(ticker)
            sector_ui = "N/A"
            industry = "N/A"
            if meta:
                sector_ui = meta.get("sector") or "N/A"
                industry = meta.get("industry") or "N/A"
                company_name = company_name or meta.get("company_name") or ticker

            # Always pull Yahoo info: the new detail columns (P/S, EV, ROE,
            # profit margin, rev growth, beta) only live in info.
            try:
                yt = yf.Ticker(ticker)
                yinfo = dict(yt.info or {})
            except Exception:
                yt = None
                yinfo = {}
            time.sleep(yahoo_delay_s)
            if not meta:
                company_name = (
                    company_name
                    or yinfo.get("shortName")
                    or yinfo.get("longName")
                    or ticker
                )
            raw_sec = yinfo.get("sector") or ""
            if raw_sec:
                sector_ui = normalize_sector(raw_sec) or sector_ui
            industry = yinfo.get("industry") or industry

            cik = get_cik_for_ticker(ticker)
            facts = get_sec_facts(cik) if cik else None

            eps = None
            shares = None
            assets = None
            liabilities = None
            equity_val = None
            revenue = None
            net_income = None

            if facts:
                eps = _first_sec_fact(
                    facts,
                    "EarningsPerShareDiluted",
                    "EarningsPerShareBasic",
                    unit="USD/shares",
                )
                shares = _first_sec_fact(
                    facts,
                    "EntityCommonStockSharesOutstanding",
                    "CommonStockSharesOutstanding",
                    unit="shares",
                )
                assets = _first_sec_fact(facts, "Assets", "AssetsCurrent", unit="USD")
                liabilities = _first_sec_fact(
                    facts, "Liabilities", "LiabilitiesCurrent", unit="USD"
                )
                equity_val = _first_sec_fact(
                    facts,
                    "StockholdersEquity",
                    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
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

            pe_ratio = None
            market_cap = None
            if price and eps and eps > 0:
                pe_ratio = round(price / float(eps), 2)
            if price and shares and shares > 0:
                market_cap = round(price * float(shares), 0)

            div_y = _safe_float(yinfo.get("dividendYield"))
            hi = _safe_float(yinfo.get("fiftyTwoWeekHigh"))
            lo = _safe_float(yinfo.get("fiftyTwoWeekLow"))

            if market_cap is None:
                cap = _safe_float(yinfo.get("marketCap"))
                if cap is not None:
                    market_cap = cap
            if pe_ratio is None:
                ype = _safe_float(yinfo.get("trailingPE")) or _safe_float(
                    yinfo.get("forwardPE")
                )
                if ype is not None and ype > 0:
                    pe_ratio = round(ype, 2)

            ps_ratio = _safe_float(yinfo.get("priceToSalesTrailing12Months"))
            enterprise_value = _safe_float(yinfo.get("enterpriseValue"))
            roe = _safe_float(yinfo.get("returnOnEquity"))
            profit_margin = _safe_float(yinfo.get("profitMargins"))
            if profit_margin is None and revenue and net_income is not None:
                try:
                    if float(revenue) != 0:
                        profit_margin = float(net_income) / float(revenue)
                except (TypeError, ValueError):
                    profit_margin = None
            beta = _safe_float(yinfo.get("beta"))

            rev_growth_yahoo = _safe_float(yinfo.get("revenueGrowth"))
            quarterly_revenue_growth = (
                round(rev_growth_yahoo * 100.0, 2) if rev_growth_yahoo is not None else None
            )

            equity_calc: float | None = None
            if assets is not None and liabilities is not None:
                try:
                    equity_calc = float(assets) - float(liabilities)
                except (TypeError, ValueError):
                    equity_calc = None
            if equity_calc is None and equity_val is not None:
                equity_calc = _safe_float(equity_val)

            radar_metrics = {
                "sector": sector_ui,
                "profit_margin": profit_margin,
                "quarterly_revenue_growth": quarterly_revenue_growth,
                "pe_ratio": pe_ratio,
            }
            pulse_vec = build_radar_pulse_inputs(
                ticker,
                radar_metrics,
                stock=yt,
                info=yinfo,
                facts=facts,
                include_momentum=False,
                revenue_sec=_safe_float(revenue) if revenue is not None else None,
            )
            radar = compute_radar_pulse(pulse_vec)

            conn.execute(
                update_sql,
                (
                    market_cap,
                    pe_ratio,
                    sector_ui,
                    industry,
                    div_y,
                    hi,
                    lo,
                    radar,
                    company_name,
                    ps_ratio,
                    enterprise_value,
                    roe,
                    profit_margin,
                    quarterly_revenue_growth,
                    _safe_float(assets),
                    _safe_float(liabilities),
                    equity_calc,
                    beta,
                    ticker,
                ),
            )
            updated += 1

            # Release large per-ticker payloads (yfinance info dict, SEC facts JSON)
            # before they accumulate. Every 25 rows we also evict the SEC cache and
            # commit so SQLite can flush its page buffer.
            yinfo = None
            facts = None
            if processed % 25 == 0:
                try:
                    get_sec_facts.cache_clear()
                except Exception:
                    pass
                conn.commit()
                gc.collect()

        conn.execute(
            """
            INSERT INTO app_meta (key, value, updated_at)
            VALUES ('fundamentals_last_run_at', ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (meta_ts, meta_ts),
        )

    return {
        "status": "ok",
        "updated": updated,
        "skipped_no_quote": skipped,
        "fundamentals_last_run_at": meta_ts,
    }


def main():
    p = argparse.ArgumentParser(description="Refresh fundamentals on stock_snapshot rows")
    p.add_argument(
        "--universe",
        choices=("mag7", "sp500", "mega", "popular", "all"),
        default="sp500",
    )
    p.add_argument(
        "--max",
        type=int,
        default=None,
        help="Process at most this many tickers (after resolve; use with --universe all)",
    )
    p.add_argument("--tickers", help="Comma-separated tickers (overrides --universe)")
    p.add_argument(
        "--yahoo-delay",
        type=float,
        default=0.35,
        help="Seconds between Yahoo metadata calls when needed",
    )
    args = p.parse_args()

    if args.tickers:
        tickers = [x.strip().upper() for x in args.tickers.split(",") if x.strip()]
    else:
        tickers = resolve_tickers(args.universe)
    if args.max is not None:
        tickers = tickers[: max(0, args.max)]

    print(refresh_fundamentals(tickers, yahoo_delay_s=args.yahoo_delay))


if __name__ == "__main__":
    main()
