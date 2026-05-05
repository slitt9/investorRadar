"""Enrich stock_snapshot with SEC-derived fundamentals + cached Yahoo metadata."""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone

import yfinance as yf

from db import ensure_schema, get_db
from metrics import compute_radar_pulse
from sec_engine import (
    extract_latest_sec_fact,
    get_cik_for_ticker,
    get_sec_facts,
    get_sp500_constituents,
    normalize_sector,
)
from universe_config import MEGA_CAP_TICKERS, POPULAR_TICKERS

yf.config.network.retries = 3


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve_tickers(mode: str) -> list[str]:
    mode = mode.strip().lower()
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
    raise ValueError(f"Unknown universe mode: {mode}")


def _yahoo_info(ticker: str) -> dict:
    try:
        stock = yf.Ticker(ticker)
        return dict(stock.info or {})
    except Exception:
        return {}


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
            company_name = COALESCE(?, company_name)
        WHERE ticker = ?
    """

    with get_db() as conn:
        for ticker in tickers:
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

            yinfo: dict = {}
            need_yahoo = meta is None or sector_ui == "N/A"
            if need_yahoo:
                yinfo = _yahoo_info(ticker)
                time.sleep(yahoo_delay_s)
                if not meta:
                    company_name = (
                        company_name
                        or yinfo.get("shortName")
                        or yinfo.get("longName")
                        or ticker
                    )
                raw_sec = yinfo.get("sector") or ""
                sector_ui = normalize_sector(raw_sec) if raw_sec else sector_ui
                industry = yinfo.get("industry") or industry

            cik = get_cik_for_ticker(ticker)
            facts = get_sec_facts(cik) if cik else None

            eps = None
            shares = None
            assets = None
            liabilities = None
            profit_margin = None

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
                ni = extract_latest_sec_fact(facts, "NetIncomeLoss", unit="USD")
                rev = extract_latest_sec_fact(facts, "Revenues", unit="USD")
                if ni is not None and rev and rev != 0:
                    profit_margin = float(ni) / float(rev)

            pe_ratio = None
            market_cap = None
            if price and eps and eps > 0:
                pe_ratio = round(price / float(eps), 2)
            if price and shares and shares > 0:
                market_cap = round(price * float(shares), 0)

            div_y = yinfo.get("dividendYield")
            hi = yinfo.get("fiftyTwoWeekHigh")
            lo = yinfo.get("fiftyTwoWeekLow")

            if market_cap is None and yinfo.get("marketCap") is not None:
                market_cap = float(yinfo["marketCap"])
            if pe_ratio is None:
                ype = yinfo.get("trailingPE") or yinfo.get("forwardPE")
                if ype is not None:
                    pe_ratio = round(float(ype), 2)
            if div_y is None and yinfo.get("dividendYield") is not None:
                div_y = yinfo.get("dividendYield")
            if hi is None and yinfo.get("fiftyTwoWeekHigh") is not None:
                hi = float(yinfo["fiftyTwoWeekHigh"])
            if lo is None and yinfo.get("fiftyTwoWeekLow") is not None:
                lo = float(yinfo["fiftyTwoWeekLow"])

            pulse_metrics = {
                "quarterly_revenue_growth": None,
                "profit_margin": profit_margin,
                "assets": assets,
                "liabilities": liabilities,
                "sector": sector_ui,
            }
            radar = compute_radar_pulse(pulse_metrics)

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
                    ticker,
                ),
            )
            updated += 1

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
        choices=("sp500", "mega", "popular"),
        default="sp500",
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

    print(refresh_fundamentals(tickers, yahoo_delay_s=args.yahoo_delay))


if __name__ == "__main__":
    main()
