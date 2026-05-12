"""Fill missing sector / market cap / P/E on screener rows returned from SQLite."""

from __future__ import annotations

import os

from cache import cached
from sec_engine import get_sp500_constituents, normalize_sector


def _sector_needs_fill(v) -> bool:
    if v is None:
        return True
    s = str(v).strip().upper()
    return s in ("", "N/A")


def _num_needs_fill(v) -> bool:
    return v is None


@cached(ttl=120)
def _live_metrics_subset(ticker: str) -> dict:
    """Light live pull for list alignment (cached per ticker)."""
    from metrics import calculate_metrics

    m = calculate_metrics(ticker.upper(), include_quarterly=False, include_sec=True)
    sec = m.get("sector") or "N/A"
    if sec and sec != "N/A":
        sec = normalize_sector(sec)
    return {
        "market_cap": m.get("market_cap"),
        "pe_ratio": m.get("pe_ratio"),
        "sector": sec,
        "industry": m.get("industry") or "N/A",
    }


def hydrate_screener_rows(rows: list[dict]) -> list[dict]:
    """Merge SP500 metadata and live Yahoo/SEC fields for rows missing snapshot data."""
    if not rows:
        return rows

    sp500 = get_sp500_constituents() or []
    sp500_meta = {c["ticker"]: c for c in sp500}

    out = []
    for row in rows:
        r = dict(row)
        t = str(r.get("ticker") or "").upper()
        if not t:
            out.append(r)
            continue

        meta = sp500_meta.get(t)
        if meta:
            if _sector_needs_fill(r.get("sector")):
                r["sector"] = meta.get("sector") or r.get("sector")
            if (not r.get("industry")) or str(r.get("industry")).strip() in ("", "N/A"):
                r["industry"] = meta.get("industry") or r.get("industry")

        need_live = (
            _num_needs_fill(r.get("market_cap"))
            or _num_needs_fill(r.get("pe_ratio"))
            or _sector_needs_fill(r.get("sector"))
        )
        if need_live and os.environ.get("SCREENER_HYDRATE_LIVE", "1").lower() in (
            "1",
            "true",
            "yes",
        ):
            try:
                live = _live_metrics_subset(t)
                if _num_needs_fill(r.get("market_cap")) and live.get("market_cap") is not None:
                    r["market_cap"] = live["market_cap"]
                if _num_needs_fill(r.get("pe_ratio")) and live.get("pe_ratio") is not None:
                    r["pe_ratio"] = live["pe_ratio"]
                if _sector_needs_fill(r.get("sector")) and live.get("sector") not in (
                    None,
                    "N/A",
                ):
                    r["sector"] = live["sector"]
                if (not r.get("industry")) or str(r.get("industry")).strip() in ("", "N/A"):
                    if live.get("industry") and live["industry"] != "N/A":
                        r["industry"] = live["industry"]
            except Exception:
                pass

        out.append(r)
    return out
