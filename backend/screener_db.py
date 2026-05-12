"""Screener rows from local SQLite snapshots (no live Yahoo on request path)."""

from __future__ import annotations

from db import ensure_schema, get_db
from sec_engine import get_sp500_constituents


def _normalize_ui_ranges(
    market_cap_min,
    market_cap_max,
    pe_min,
    pe_max,
    volume_min,
    volume_max,
    price_min,
    price_max,
):
    UI_MAX_MARKET_CAP = 2_000_000_000_000
    UI_MAX_PE = 80
    UI_MAX_VOLUME = 100_000_000
    UI_MAX_PRICE = 600

    def norm(min_v, max_v, ui_max):
        if min_v is not None and min_v <= 0:
            min_v = None
        if max_v is not None and max_v >= ui_max:
            max_v = None
        return min_v, max_v

    return (
        *norm(market_cap_min, market_cap_max, UI_MAX_MARKET_CAP),
        *norm(pe_min, pe_max, UI_MAX_PE),
        *norm(volume_min, volume_max, UI_MAX_VOLUME),
        *norm(price_min, price_max, UI_MAX_PRICE),
    )


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
    """Return screener rows from stock_snapshot joined with stock_universe for names.

    When ``meta_source == "sp500"`` we also LEFT JOIN a temp S&P 500 metadata
    table so the SQL itself can COALESCE sector / industry for constituents
    that have not been enriched yet.
    """

    return_limit = max(0, int(limit))
    tickers = list(tickers)
    if eval_limit is not None:
        tickers = tickers[: max(0, int(eval_limit))]
    if not tickers:
        return []

    (
        market_cap_min,
        market_cap_max,
        pe_min,
        pe_max,
        volume_min,
        volume_max,
        price_min,
        price_max,
    ) = _normalize_ui_ranges(
        market_cap_min,
        market_cap_max,
        pe_min,
        pe_max,
        volume_min,
        volume_max,
        price_min,
        price_max,
    )

    where = ["s.ticker IN (SELECT ticker FROM _screener_universe_filter)"]

    args: list = []

    sector_expr = "COALESCE(NULLIF(s.sector, 'N/A'), s.sector, sp.sector)"

    if sector and sector != "All":
        if sector == "Other":
            where.append(
                f"({sector_expr} = 'Other' OR {sector_expr} IS NULL OR TRIM(COALESCE({sector_expr},'')) = '' OR {sector_expr} = 'N/A')"
            )
        else:
            where.append(f"{sector_expr} = ?")
            args.append(sector)

    if dividends_only:
        where.append("COALESCE(s.dividend_yield, 0) > 0")

    def add_range(col, lo, hi):
        # Match live screener: NULL metric does not fail the filter.
        if lo is not None:
            where.append(f"({col} IS NULL OR {col} >= ?)")
            args.append(lo)
        if hi is not None:
            where.append(f"({col} IS NULL OR {col} <= ?)")
            args.append(hi)

    add_range("s.market_cap", market_cap_min, market_cap_max)
    add_range("s.pe_ratio", pe_min, pe_max)
    add_range("s.volume", volume_min, volume_max)
    add_range("s.price", price_min, price_max)

    use_sp500_meta = (meta_source or "").lower() == "sp500"

    sql = f"""
        SELECT
            s.ticker AS ticker,
            COALESCE(NULLIF(s.company_name, ''), u.company_name, sp.company_name, s.ticker) AS company_name,
            s.price AS price,
            s.pct_change AS pct_change,
            s.volume AS volume,
            s.market_cap AS market_cap,
            s.pe_ratio AS pe_ratio,
            COALESCE(NULLIF(s.sector, 'N/A'), s.sector, sp.sector) AS sector,
            COALESCE(NULLIF(s.industry, 'N/A'), s.industry, sp.industry) AS industry,
            s.dividend_yield AS dividend_yield,
            s.fifty_two_week_high AS fifty_two_week_high,
            s.fifty_two_week_low AS fifty_two_week_low,
            s.radar_pulse AS radar_pulse
        FROM stock_snapshot s
        LEFT JOIN stock_universe u ON u.ticker = s.ticker
        LEFT JOIN _screener_sp500_meta sp ON sp.ticker = s.ticker
        WHERE {' AND '.join(where)}
          AND s.price IS NOT NULL
        ORDER BY (s.pct_change IS NULL) ASC, s.pct_change DESC
        LIMIT ?
    """
    args.append(return_limit)

    ensure_schema()
    with get_db() as conn:
        conn.execute("DROP TABLE IF EXISTS _screener_universe_filter")
        conn.execute(
            "CREATE TEMP TABLE _screener_universe_filter (ticker TEXT PRIMARY KEY)"
        )
        conn.executemany(
            "INSERT OR IGNORE INTO _screener_universe_filter (ticker) VALUES (?)",
            [(t,) for t in tickers],
        )

        conn.execute("DROP TABLE IF EXISTS _screener_sp500_meta")
        conn.execute(
            """
            CREATE TEMP TABLE _screener_sp500_meta (
                ticker TEXT PRIMARY KEY,
                company_name TEXT,
                sector TEXT,
                industry TEXT
            )
            """
        )
        if use_sp500_meta:
            try:
                sp500 = get_sp500_constituents() or []
            except Exception:
                sp500 = []
            if sp500:
                conn.executemany(
                    "INSERT OR IGNORE INTO _screener_sp500_meta (ticker, company_name, sector, industry) VALUES (?, ?, ?, ?)",
                    [
                        (
                            c.get("ticker"),
                            c.get("company_name"),
                            c.get("sector"),
                            c.get("industry"),
                        )
                        for c in sp500
                        if c.get("ticker")
                    ],
                )

        rows = conn.execute(sql, args).fetchall()

    out = []
    for r in rows:
        d = dict(r)
        for k in ("price", "pct_change", "market_cap", "pe_ratio", "dividend_yield",
                  "fifty_two_week_high", "fifty_two_week_low"):
            v = d.get(k)
            if v is not None and k in ("price", "pct_change") and isinstance(v, float):
                d[k] = round(v, 2)
        out.append(d)
    return out
