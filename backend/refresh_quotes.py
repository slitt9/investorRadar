"""Batch-download prices into stock_snapshot (quote fields only)."""

from __future__ import annotations

import argparse
import gc
import os
import time
from datetime import datetime, timezone

import yfinance as yf

from db import ensure_schema, get_db
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


def _chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _download_chunk(symbols: list[str]) -> dict[str, tuple[float, float, float, int | None]]:
    if not symbols:
        return {}
    try:
        df = yf.download(
            " ".join(symbols),
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
    out: dict[str, tuple[float, float, float, int | None]] = {}
    for t in symbols:
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
            pct = ((close - prev) / prev) * 100.0
            vol = int(sub["Volume"].iloc[-1]) if "Volume" in sub.columns else None
            out[t] = (close, prev, pct, vol)
        except Exception:
            continue
    return out


def _enrich_market_cap_and_pe(
    conn,
    ticker: str,
    *,
    valuation_sleep_s: float,
) -> None:
    """Fill market_cap (Yahoo fast_info), pe_ratio (price / SEC EPS) and
    sector / industry (Yahoo info, normalized) on snapshot rows."""
    time.sleep(valuation_sleep_s)
    row = conn.execute(
        "SELECT price, sector, industry FROM stock_snapshot WHERE ticker = ?",
        (ticker,),
    ).fetchone()
    if not row or row["price"] is None:
        return
    price = float(row["price"])
    mcap = None
    pe = None
    sector_ui = None
    industry_val = None

    yf_ticker = None
    try:
        yf_ticker = yf.Ticker(ticker)
        cap = yf_ticker.fast_info.get("marketCap")
        if cap is not None:
            mcap = float(cap)
    except Exception:
        pass

    have_sector = row["sector"] not in (None, "", "N/A")
    have_industry = row["industry"] not in (None, "", "N/A")
    if (not have_sector or not have_industry) and yf_ticker is not None:
        try:
            info = yf_ticker.info or {}
            if not have_sector:
                raw_sec = info.get("sector") or ""
                if raw_sec:
                    sector_ui = normalize_sector(raw_sec)
            if not have_industry:
                raw_ind = info.get("industry") or ""
                if raw_ind:
                    industry_val = raw_ind
        except Exception:
            pass

    try:
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
                if eps is not None and float(eps) > 0:
                    pe = round(price / float(eps), 2)
    except Exception:
        pass
    if mcap is None and pe is None and sector_ui is None and industry_val is None:
        return
    conn.execute(
        """
        UPDATE stock_snapshot SET
            market_cap = COALESCE(?, market_cap),
            pe_ratio   = COALESCE(?, pe_ratio),
            sector     = COALESCE(NULLIF(NULLIF(sector, 'N/A'), ''), ?, sector),
            industry   = COALESCE(NULLIF(NULLIF(industry, 'N/A'), ''), ?, industry)
        WHERE ticker = ?
        """,
        (mcap, pe, sector_ui, industry_val, ticker),
    )


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


def refresh_quotes(
    tickers: list[str],
    *,
    chunk_size: int = 40,
    sleep_s: float = 0.2,
    enrich_valuation: bool | None = None,
    valuation_sleep_s: float | None = None,
) -> dict:
    """Upsert quote fields on stock_snapshot for each ticker."""
    ensure_schema()
    as_of = _utc_now_iso()
    tickers = [t.upper().strip() for t in tickers if t and str(t).strip()]
    if not tickers:
        return {"status": "noop", "updated": 0, "as_of": as_of}

    snapshots: dict[str, tuple[float, float, float, int | None]] = {}
    for chunk in _chunks(tickers, chunk_size):
        snapshots.update(_download_chunk(chunk))
        time.sleep(sleep_s)

    missing = [t for t in tickers if t not in snapshots]
    for chunk in _chunks(missing, 12):
        snapshots.update(_download_chunk(chunk))
        time.sleep(sleep_s)

    upsert_sql = """
        INSERT INTO stock_snapshot (
            ticker, as_of, price, prev_close, pct_change, volume
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            as_of = excluded.as_of,
            price = excluded.price,
            prev_close = excluded.prev_close,
            pct_change = excluded.pct_change,
            volume = excluded.volume
    """

    if enrich_valuation is None:
        enrich_valuation = os.environ.get("QUOTE_REFRESH_SKIP_VALUATION", "").lower() not in (
            "1",
            "true",
            "yes",
        )
    if valuation_sleep_s is None:
        valuation_sleep_s = float(os.environ.get("QUOTE_VALUATION_SLEEP", "0.08"))

    n = 0
    with get_db() as conn:
        for t, (close, prev, pct, vol) in snapshots.items():
            conn.execute(
                upsert_sql,
                (t, as_of, close, prev, round(pct, 2), vol),
            )
            n += 1
        # Free the bulk-download DataFrame contents before the long enrich loop.
        snapshot_tickers = sorted(snapshots.keys())
        snapshots.clear()
        gc.collect()

        if enrich_valuation and snapshot_tickers:
            for idx, t in enumerate(snapshot_tickers, 1):
                _enrich_market_cap_and_pe(conn, t, valuation_sleep_s=valuation_sleep_s)
                if idx % 25 == 0:
                    # Drop cached SEC facts (10-30 MB each) and reclaim yfinance internals.
                    try:
                        get_sec_facts.cache_clear()
                    except Exception:
                        pass
                    conn.commit()
                    gc.collect()
        conn.execute(
            """
            INSERT INTO app_meta (key, value, updated_at)
            VALUES ('quotes_last_run_at', ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (as_of, as_of),
        )

    return {"status": "ok", "updated": n, "as_of": as_of, "requested": len(tickers)}


def main():
    p = argparse.ArgumentParser(description="Refresh quote fields in stock_snapshot")
    p.add_argument(
        "--universe",
        choices=("mag7", "sp500", "mega", "popular", "all"),
        default="sp500",
        help="Which ticker list to refresh (all = searchable equities, cap from REFRESH_ALL_CAP)",
    )
    p.add_argument(
        "--tickers",
        help="Comma-separated tickers (overrides --universe)",
    )
    p.add_argument(
        "--no-valuation",
        action="store_true",
        help="Skip Yahoo market cap + SEC P/E enrichment (faster; grid may show — for cap/P/E)",
    )
    args = p.parse_args()

    if args.tickers:
        tickers = [x.strip().upper() for x in args.tickers.split(",") if x.strip()]
    else:
        tickers = resolve_tickers(args.universe)

    result = refresh_quotes(tickers, enrich_valuation=not args.no_valuation)
    print(result)


if __name__ == "__main__":
    main()
