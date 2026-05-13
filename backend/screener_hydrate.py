"""Fill missing sector / market cap / P/E on screener rows returned from SQLite.

Strategy (matches what /api/quote shows the user):

1. Cheap, always-on: merge S&P 500 Wikipedia metadata for sector/industry.
2. Bounded live pull (capped at ``SCREENER_HYDRATE_MAX``, default 25 rows per
   request) that mirrors ``metrics.calculate_metrics``:

   - Market cap: SEC ``EntityCommonStockSharesOutstanding`` x snapshot price,
     falling back to ``yfinance.Ticker.info['marketCap']``, then
     ``fast_info.marketCap``.
   - P/E: snapshot price / SEC EPS (diluted, then basic), falling back to
     ``info['trailingPE']`` then ``info['forwardPE']``.
   - Sector / industry: ``info['sector']`` / ``info['industry']``, normalized
     via ``sec_engine.normalize_sector``.

3. Persist filled values back to ``stock_snapshot`` via a ``COALESCE`` UPDATE
   so subsequent requests are served entirely from SQLite. Empty results are
   cached for a short window (60s) so transient Yahoo failures retry quickly;
   successful results are cached for 15 minutes.
"""

from __future__ import annotations

import logging
import os
import time
from threading import Lock

from db import ensure_schema, get_db
from sec_engine import (
    extract_latest_sec_fact,
    get_cik_for_ticker,
    get_sec_facts,
    get_sp500_constituents,
    normalize_sector,
)

log = logging.getLogger(__name__)

_EMPTY_KEYS = ("market_cap", "pe_ratio", "sector", "industry")

_metrics_cache: dict[str, tuple[dict, float]] = {}
_metrics_lock = Lock()


def _sector_needs_fill(v) -> bool:
    if v is None:
        return True
    s = str(v).strip().upper()
    return s in ("", "N/A")


def _num_needs_fill(v) -> bool:
    return v is None


def _truthy(env_value: str | None) -> bool:
    return (env_value or "").strip().lower() in ("1", "true", "yes")


def _is_empty(out: dict) -> bool:
    return all(out.get(k) is None for k in _EMPTY_KEYS)


def _compute_live_metrics(ticker: str, price_hint: float | None) -> dict:
    """Single live pull that mirrors ``/api/quote`` for the fields we need.

    Tries SEC (most accurate, matches popup) first, then ``info`` (always
    populated for liquid tickers), then ``fast_info``. Any field we can fill
    is returned; missing fields stay None.
    """
    import yfinance as yf

    out: dict = {k: None for k in _EMPTY_KEYS}

    # --- SEC: price * shares (cap) and price / EPS (P/E) -----------------
    sec_shares: float | None = None
    sec_eps: float | None = None
    try:
        cik = get_cik_for_ticker(ticker)
        if cik:
            facts = get_sec_facts(cik)
            if facts:
                try:
                    shares = extract_latest_sec_fact(
                        facts, "EntityCommonStockSharesOutstanding", unit="shares"
                    )
                    if shares is None:
                        shares = extract_latest_sec_fact(
                            facts, "CommonStockSharesOutstanding", unit="shares"
                        )
                    if shares is not None and float(shares) > 0:
                        sec_shares = float(shares)
                except Exception:
                    pass

                try:
                    eps = extract_latest_sec_fact(
                        facts, "EarningsPerShareDiluted", unit="USD/shares"
                    )
                    if eps is None:
                        eps = extract_latest_sec_fact(
                            facts, "EarningsPerShareBasic", unit="USD/shares"
                        )
                    if eps is not None and float(eps) > 0:
                        sec_eps = float(eps)
                except Exception:
                    pass
    except Exception as exc:
        log.debug("hydrate sec(%s) failed: %s", ticker, exc)

    if (
        sec_shares is not None
        and price_hint is not None
        and float(price_hint) > 0
    ):
        out["market_cap"] = round(float(price_hint) * sec_shares, 0)
    if (
        sec_eps is not None
        and price_hint is not None
        and float(price_hint) > 0
    ):
        out["pe_ratio"] = round(float(price_hint) / sec_eps, 2)

    # --- Yahoo info: cap / PE / sector / industry ------------------------
    info: dict = {}
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception as exc:
        log.debug("hydrate info(%s) failed: %s", ticker, exc)
        info = {}

    if out["market_cap"] is None:
        try:
            cap = info.get("marketCap")
            if cap is not None:
                out["market_cap"] = float(cap)
        except Exception:
            pass

    if out["pe_ratio"] is None:
        try:
            pe = info.get("trailingPE") or info.get("forwardPE")
            if pe is not None:
                pe_f = float(pe)
                if pe_f > 0:
                    out["pe_ratio"] = round(pe_f, 2)
        except Exception:
            pass

    try:
        raw_sector = info.get("sector") or ""
        if raw_sector:
            out["sector"] = normalize_sector(raw_sector)
    except Exception:
        pass

    try:
        raw_industry = info.get("industry") or ""
        if raw_industry:
            out["industry"] = raw_industry
    except Exception:
        pass

    # --- fast_info fallback for cap --------------------------------------
    if out["market_cap"] is None:
        try:
            fi = yf.Ticker(ticker).fast_info
            cap = None
            if hasattr(fi, "get"):
                cap = fi.get("marketCap") or fi.get("market_cap")
            if cap is None:
                cap = getattr(fi, "market_cap", None) or getattr(
                    fi, "marketCap", None
                )
            if cap is not None:
                out["market_cap"] = float(cap)
        except Exception as exc:
            log.debug("hydrate fast_info(%s) failed: %s", ticker, exc)

    return out


def _cached_live_metrics(ticker: str, price_hint: float | None) -> dict:
    """Wrapped compute that retries empty results quickly but caches positives."""
    try:
        positive_ttl = int(os.environ.get("SCREENER_HYDRATE_TTL", "900"))
    except ValueError:
        positive_ttl = 900
    try:
        empty_ttl = int(os.environ.get("SCREENER_HYDRATE_EMPTY_TTL", "60"))
    except ValueError:
        empty_ttl = 60

    now = time.time()
    with _metrics_lock:
        entry = _metrics_cache.get(ticker)
        if entry and entry[1] > now:
            return entry[0]

    fresh = _compute_live_metrics(ticker, price_hint)
    with _metrics_lock:
        _metrics_cache[ticker] = (
            fresh,
            now + (empty_ttl if _is_empty(fresh) else positive_ttl),
        )
    return fresh


def _persist_row(
    conn, ticker: str, *, market_cap, pe_ratio, sector, industry
) -> None:
    if all(v is None for v in (market_cap, pe_ratio, sector, industry)):
        return
    try:
        conn.execute(
            """
            UPDATE stock_snapshot SET
                market_cap = COALESCE(market_cap, ?),
                pe_ratio   = COALESCE(pe_ratio, ?),
                sector     = COALESCE(NULLIF(NULLIF(sector, 'N/A'), ''), ?, sector),
                industry   = COALESCE(NULLIF(NULLIF(industry, 'N/A'), ''), ?, industry)
            WHERE ticker = ?
            """,
            (market_cap, pe_ratio, sector, industry, ticker),
        )
    except Exception as exc:
        log.warning("hydrate persist(%s) failed: %s", ticker, exc)


def hydrate_screener_rows(rows: list[dict]) -> list[dict]:
    """Fill sector / market_cap / pe_ratio for rows that need it."""
    if not rows:
        return rows

    sp500 = []
    try:
        sp500 = get_sp500_constituents() or []
    except Exception as exc:
        log.debug("hydrate sp500 list failed: %s", exc)
    sp500_meta = {c["ticker"]: c for c in sp500 if c.get("ticker")}

    live_enabled = _truthy(os.environ.get("SCREENER_HYDRATE_LIVE", "1"))
    try:
        live_cap = int(os.environ.get("SCREENER_HYDRATE_MAX", "25"))
    except ValueError:
        live_cap = 25
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
                live = _cached_live_metrics(t, r.get("price"))
            except Exception as exc:
                log.warning("hydrate live(%s) failed: %s", t, exc)
                live = {k: None for k in _EMPTY_KEYS}

            new_cap = None
            new_pe = None
            new_sector = None
            new_industry = None

            if _num_needs_fill(r.get("market_cap")) and live.get("market_cap") is not None:
                r["market_cap"] = live["market_cap"]
                new_cap = live["market_cap"]
            if _num_needs_fill(r.get("pe_ratio")) and live.get("pe_ratio") is not None:
                r["pe_ratio"] = live["pe_ratio"]
                new_pe = live["pe_ratio"]
            if _sector_needs_fill(r.get("sector")) and live.get("sector"):
                r["sector"] = live["sector"]
                new_sector = live["sector"]
            if _sector_needs_fill(r.get("industry")) and live.get("industry"):
                r["industry"] = live["industry"]
                new_industry = live["industry"]

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
            log.info(
                "hydrate: persisted %d rows (live_used=%d)",
                len(pending_writes),
                live_used,
            )
        except Exception as exc:
            log.warning("hydrate persist batch failed: %s", exc)

    return out
