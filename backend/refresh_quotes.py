"""Batch-download prices into stock_snapshot (quote fields only)."""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone

import yfinance as yf

from db import ensure_schema, get_db
from sec_engine import get_sp500_constituents
from universe_config import MEGA_CAP_TICKERS, POPULAR_TICKERS

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


def refresh_quotes(
    tickers: list[str],
    *,
    chunk_size: int = 40,
    sleep_s: float = 0.2,
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

    n = 0
    with get_db() as conn:
        for t, (close, prev, pct, vol) in snapshots.items():
            conn.execute(
                upsert_sql,
                (t, as_of, close, prev, round(pct, 2), vol),
            )
            n += 1
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
        choices=("sp500", "mega", "popular"),
        default="sp500",
        help="Which ticker list to refresh",
    )
    p.add_argument(
        "--tickers",
        help="Comma-separated tickers (overrides --universe)",
    )
    args = p.parse_args()

    if args.tickers:
        tickers = [x.strip().upper() for x in args.tickers.split(",") if x.strip()]
    else:
        tickers = resolve_tickers(args.universe)

    result = refresh_quotes(tickers)
    print(result)


if __name__ == "__main__":
    main()
