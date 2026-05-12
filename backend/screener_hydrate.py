"""Fill missing sector / market cap / P/E on screener rows returned from SQLite.

Strategy (fast + durable):

1. Cheap, always-on: merge S&P 500 Wikipedia metadata for sector/industry.
2. Bounded live pull (capped at ``SCREENER_HYDRATE_MAX``, default 30 rows per
   request) using ``yfinance.fast_info`` for market cap and SEC EPS for P/E.
   Falls back to a single ``yf.Ticker(t).info`` call only when sector is still
   missing.
3. Persist filled values back to ``stock_snapshot`` via a ``COALESCE`` UPDATE
   so subsequent requests are served entirely from SQLite.
"""

from __future__ import annotations

import logging
import os
import time

from cache import cached
from db import ensure_schema, get_db
from sec_engine import (
    extract_latest_sec_fact,
    get_cik_for_ticker,
    get_sec_facts,
    get_sp500_constituents,
    normalize_sector,
)

log = logging.getLogger(__name__)


def _sector_needs_fill(v) -> bool:
    if v is None:
        return True
    s = str(v).strip().upper()
    return s in ("", "N/A")


def _num_needs_fill(v) -> bool:
    return v is None


def _truthy(env_value: str | None) -> bool:
    return (env_value or "").strip().lower() in ("1", "true", "yes")


@cached(ttl=900)
def _live_fast_metrics(ticker: str, price_hint: float | None) -> dict:
    """Light live pull: fast_info (cap) + SEC EPS (P/E). Cached per ticker.

    ``price_hint`` is the snapshot price used to compute P/E (avoids an extra
    history fetch). When unavailable we skip P/E computation.
    """
    import yfinance as yf

    out: dict = {
        "market_cap": None,
        "pe_ratio": None,
        "sector": None,
        "industry": None,
    }

    try:
        fi = yf.Ticker(ticker).fast_info
        cap = fi.get("marketCap") if hasattr(fi, "get") else None
        if cap is not None:
            out["market_cap"] = float(cap)
    except Exception as exc:
        log.warning("hydrate fast_info(%s) failed: %s", ticker, exc)

    if price_hint and price_hint > 0:
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
                        out["pe_ratio"] = round(float(price_hint) / float(eps), 2)
        except Exception as exc:
            log.warning("hydrate sec_eps(%s) failed: %s", ticker, exc)

    return out


@cached(ttl=900)
def _live_sector_industry(ticker: str) -> dict:
    """Single ``Ticker.info`` call to recover sector/industry. Cached per ticker."""
    import yfinance as yf

    try:
        info = yf.Ticker(ticker).info or {}
        raw_sector = info.get("sector") or ""
        raw_industry = info.get("industry") or ""
        return {
            "sector": normalize_sector(raw_sector) if raw_sector else None,
            "industry": raw_industry or None,
        }
    except Exception as exc:
        log.warning("hydrate info(%s) failed: %s", ticker, exc)
        return {"sector": None, "industry": None}


def _persist_row(conn, ticker: str, *, market_cap, pe_ratio, sector, industry) -> None:
    if all(v is None for v in (market_cap, pe_ratio, sector, industry)):
        return
    try:
        conn.execute(
            """
            UPDATE stock_snapshot SET
                market_cap = COALESCE(market_cap, ?),
                pe_ratio   = COALESCE(pe_ratio, ?),
                sector     = COALESCE(NULLIF(sector, 'N/A'), sector, ?),
                industry   = COALESCE(NULLIF(industry, 'N/A'), industry, ?)
            WHERE ticker = ?
            """,
            (market_cap, pe_ratio, sector, industry, ticker),
        )
    except Exception as exc:
        log.warning("hydrate persist(%s) failed: %s", ticker, exc)


def hydrate_screener_rows(rows: list[dict]) -> list[dict]:
    """Fill sector / market_cap / pe_ratio for rows that need it.

    - Cheap S&P 500 metadata merge is always applied.
    - Live calls (``yfinance``) are gated by ``SCREENER_HYDRATE_LIVE`` (default
      on) and capped at ``SCREENER_HYDRATE_MAX`` rows per request.
    - Filled values are persisted back to ``stock_snapshot``.
    """
    if not rows:
        return rows

    sp500 = get_sp500_constituents() or []
    sp500_meta = {c["ticker"]: c for c in sp500}

    live_enabled = _truthy(os.environ.get("SCREENER_HYDRATE_LIVE", "1"))
    try:
        live_cap = int(os.environ.get("SCREENER_HYDRATE_MAX", "30"))
    except ValueError:
        live_cap = 30
    try:
        live_sleep = float(os.environ.get("SCREENER_HYDRATE_SLEEP", "0.05"))
    except ValueError:
        live_sleep = 0.05

    out: list[dict] = []
    live_used = 0
    pending_writes: list[tuple] = []

    for row in rows:
        r = dict(row)
        t = str(r.get("ticker") or "").upper()
        if not t:
            out.append(r)
            continue

        meta = sp500_meta.get(t)
        if meta:
            if _sector_needs_fill(r.get("sector")) and meta.get("sector"):
                r["sector"] = meta["sector"]
            if _sector_needs_fill(r.get("industry")) and meta.get("industry"):
                r["industry"] = meta["industry"]

        need_live = (
            _num_needs_fill(r.get("market_cap"))
            or _num_needs_fill(r.get("pe_ratio"))
            or _sector_needs_fill(r.get("sector"))
        )

        if need_live and live_enabled and live_used < live_cap:
            live_used += 1
            try:
                fast = _live_fast_metrics(t, r.get("price"))
            except Exception as exc:
                log.warning("hydrate live(%s) failed: %s", t, exc)
                fast = {"market_cap": None, "pe_ratio": None}

            new_cap = None
            new_pe = None
            new_sector = None
            new_industry = None

            if _num_needs_fill(r.get("market_cap")) and fast.get("market_cap") is not None:
                r["market_cap"] = fast["market_cap"]
                new_cap = fast["market_cap"]
            if _num_needs_fill(r.get("pe_ratio")) and fast.get("pe_ratio") is not None:
                r["pe_ratio"] = fast["pe_ratio"]
                new_pe = fast["pe_ratio"]

            if _sector_needs_fill(r.get("sector")) or _sector_needs_fill(r.get("industry")):
                info = _live_sector_industry(t)
                if _sector_needs_fill(r.get("sector")) and info.get("sector"):
                    r["sector"] = info["sector"]
                    new_sector = info["sector"]
                if _sector_needs_fill(r.get("industry")) and info.get("industry"):
                    r["industry"] = info["industry"]
                    new_industry = info["industry"]

            if any(v is not None for v in (new_cap, new_pe, new_sector, new_industry)):
                pending_writes.append((t, new_cap, new_pe, new_sector, new_industry))

            if live_sleep > 0:
                time.sleep(live_sleep)

        out.append(r)

    if pending_writes:
        try:
            ensure_schema()
            with get_db() as conn:
                for t, mcap, pe, sec, ind in pending_writes:
                    _persist_row(
                        conn,
                        t,
                        market_cap=mcap,
                        pe_ratio=pe,
                        sector=sec,
                        industry=ind,
                    )
        except Exception as exc:
            log.warning("hydrate persist batch failed: %s", exc)

    return out
