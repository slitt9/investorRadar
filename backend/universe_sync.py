"""Universe import and search utilities for the local screener dataset."""

from __future__ import annotations

import csv
import io
import os
import threading
from datetime import datetime, timedelta, timezone

import requests

from db import ensure_schema, get_db
from sec_engine import get_sec_tickers_list

NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
SYNC_META_KEY = "stock_universe_last_synced_at"

SYNC_HEADERS = {"User-Agent": "InvestorRadarApp admin@investorradar.com"}

# Nasdaq symbol directory changes infrequently; default 72h unless overridden.
_UNIVERSE_STALE_HOURS = int(os.environ.get("UNIVERSE_STALE_HOURS", "72"))

_sync_lock = threading.Lock()

_EXCHANGE_LABELS = {
    "A": "NYSE American",
    "N": "NYSE",
    "P": "NYSE Arca",
    "Q": "Nasdaq",
    "V": "IEX",
    "Z": "Cboe",
}

_EXCLUDED_NAME_TOKENS = (
    " ETF",
    " ETN",
    " FUND",
    " TRUST",
    " WARRANT",
    " WTS",
    " RIGHT",
    " RIGHTS",
    " UNIT",
    " UNITS",
    " PREFERRED",
    " PREFERENCE",
    " DEPOSITARY SHARE",
    " DEPOSITORY SHARE",
    " NOTE",
    " NOTES",
    " BOND",
    " BONDS",
    " DEBENTURE",
    " NEXTSHARES",
)

_COMMON_EQUITY_MARKERS = (
    "COMMON STOCK",
    "COMMON SHARES",
    "COMMON SHARE",
    "CLASS A COMMON",
    "CLASS B COMMON",
    "ORDINARY SHARE",
    "ORDINARY SHARES",
    "AMERICAN DEPOSITARY SHARES",
    "ADS",
    "ADR",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_symbol(symbol: str | None) -> str:
    return (
        (symbol or "")
        .strip()
        .upper()
        .replace(".", "-")
        .replace("/", "-")
        .replace(" ", "")
    )


def _normalize_name(name: str | None) -> str:
    return " ".join((name or "").upper().split())


def _parse_pipe_rows(text: str) -> list[dict[str, str]]:
    rows = []
    reader = csv.DictReader(io.StringIO(text), delimiter="|")
    for row in reader:
        if not row:
            continue
        values = list(row.values())
        if values and values[0] and values[0].startswith("File Creation Time"):
            continue
        rows.append({k: (v or "").strip() for k, v in row.items() if k})
    return rows


def _fetch_pipe_rows(url: str) -> list[dict[str, str]]:
    resp = requests.get(url, headers=SYNC_HEADERS, timeout=30)
    resp.raise_for_status()
    return _parse_pipe_rows(resp.text)


def _classify_security(name: str, *, is_etf: bool) -> tuple[str, bool]:
    upper_name = _normalize_name(name)
    if is_etf:
        return "etf", False

    for token in _EXCLUDED_NAME_TOKENS:
        if token in upper_name:
            if "TRUST" in token and "REALTY TRUST" in upper_name:
                break
            return token.strip().lower().replace(" ", "_"), False

    if any(marker in upper_name for marker in _COMMON_EQUITY_MARKERS):
        if "ADR" in upper_name or "AMERICAN DEPOSITARY SHARES" in upper_name:
            return "adr", True
        if "ORDINARY" in upper_name:
            return "ordinary", True
        return "common", True

    if "HOLDINGS" in upper_name or "CORP" in upper_name or "CORPORATION" in upper_name:
        return "common", True
    if "INC" in upper_name or "PLC" in upper_name or "LTD" in upper_name or "LIMITED" in upper_name:
        return "common", True
    if "GROUP" in upper_name or "CO." in upper_name or "COMPANY" in upper_name:
        return "common", True
    if "REIT" in upper_name or "REALTY TRUST" in upper_name:
        return "reit", True
    if "L.P." in upper_name or "LP" in upper_name or "PARTNERS" in upper_name:
        return "partnership", True

    return "other_equity", True


def _merge_sec_metadata(rows: dict[str, dict[str, object]]) -> None:
    for item in get_sec_tickers_list():
        ticker = _normalize_symbol(item.get("ticker"))
        if not ticker or ticker not in rows:
            continue
        title = (item.get("name") or "").strip()
        if title:
            rows[ticker]["company_name"] = title


def _fetch_sec_cik_map() -> dict[str, str]:
    cik_map = {}
    for item in get_sec_tickers_list():
        ticker = _normalize_symbol(item.get("ticker"))
        cik = item.get("cik")
        if ticker and cik:
            cik_map[ticker] = str(cik)
    return cik_map


def build_stock_universe() -> list[dict[str, object]]:
    sec_rows = get_sec_tickers_list()
    sec_name_map = {
        _normalize_symbol(item.get("ticker")): (item.get("name") or "").strip()
        for item in sec_rows
        if _normalize_symbol(item.get("ticker"))
    }

    records: dict[str, dict[str, object]] = {}

    for row in _fetch_pipe_rows(NASDAQ_LISTED_URL):
        ticker = _normalize_symbol(row.get("Symbol"))
        if not ticker:
            continue

        security_name = (row.get("Security Name") or "").strip()
        is_etf = (row.get("ETF") or "").upper() == "Y"
        is_test_issue = (row.get("Test Issue") or "").upper() == "Y"
        security_type, is_searchable = _classify_security(security_name, is_etf=is_etf)
        company_name = sec_name_map.get(ticker) or security_name.split(" - ")[0].strip() or ticker

        records[ticker] = {
            "ticker": ticker,
            "company_name": company_name,
            "normalized_name": _normalize_name(company_name),
            "exchange": _EXCHANGE_LABELS.get("Q", "Nasdaq"),
            "exchange_code": "Q",
            "security_name": security_name or company_name,
            "security_type": security_type,
            "is_etf": 1 if is_etf else 0,
            "is_active": 0 if is_test_issue else 1,
            "is_searchable": 1 if (is_searchable and not is_test_issue) else 0,
            "cik": None,
            "source": "nasdaqtrader:nasdaqlisted",
        }

    for row in _fetch_pipe_rows(OTHER_LISTED_URL):
        ticker = _normalize_symbol(row.get("NASDAQ Symbol") or row.get("ACT Symbol"))
        if not ticker:
            continue

        exchange_code = (row.get("Exchange") or "").upper().strip()
        exchange = _EXCHANGE_LABELS.get(exchange_code, exchange_code or "Other")
        security_name = (row.get("Security Name") or "").strip()
        is_etf = (row.get("ETF") or "").upper() == "Y"
        is_test_issue = (row.get("Test Issue") or "").upper() == "Y"
        security_type, is_searchable = _classify_security(security_name, is_etf=is_etf)
        company_name = sec_name_map.get(ticker) or security_name.split(" - ")[0].strip() or ticker

        records[ticker] = {
            "ticker": ticker,
            "company_name": company_name,
            "normalized_name": _normalize_name(company_name),
            "exchange": exchange,
            "exchange_code": exchange_code,
            "security_name": security_name or company_name,
            "security_type": security_type,
            "is_etf": 1 if is_etf else 0,
            "is_active": 0 if is_test_issue else 1,
            "is_searchable": 1 if (is_searchable and not is_test_issue) else 0,
            "cik": None,
            "source": "nasdaqtrader:otherlisted",
        }

    cik_map = {}
    try:
        resp = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers=SYNC_HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        for item in data.values():
            ticker = _normalize_symbol(item.get("ticker"))
            if ticker:
                cik_map[ticker] = str(item.get("cik_str", "")).zfill(10)
                if ticker in records and item.get("title"):
                    title = str(item["title"]).strip()
                    records[ticker]["company_name"] = title
                    records[ticker]["normalized_name"] = _normalize_name(title)
    except Exception:
        cik_map = {}

    updated_at = _utc_now_iso()
    out = []
    for record in records.values():
        ticker = str(record["ticker"])
        record["cik"] = cik_map.get(ticker)
        record["updated_at"] = updated_at
        out.append(record)

    out.sort(key=lambda row: str(row["ticker"]))
    return out


def _get_last_sync_ts(conn) -> datetime | None:
    row = conn.execute(
        "SELECT value FROM app_meta WHERE key = ?",
        (SYNC_META_KEY,),
    ).fetchone()
    if not row:
        return None
    try:
        return datetime.fromisoformat(row["value"])
    except Exception:
        return None


def get_universe_count() -> int:
    ensure_schema()
    with get_db() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM stock_universe").fetchone()
        return int(row["count"] if row else 0)


def sync_stock_universe(*, force: bool = False) -> dict[str, object]:
    ensure_schema()
    with _sync_lock:
        with get_db() as conn:
            if not force:
                last_sync = _get_last_sync_ts(conn)
                count_row = conn.execute(
                    "SELECT COUNT(*) AS count FROM stock_universe"
                ).fetchone()
                count = int(count_row["count"] if count_row else 0)
                if count > 0 and last_sync and datetime.now(timezone.utc) - last_sync < timedelta(
                    hours=_UNIVERSE_STALE_HOURS
                ):
                    return {
                        "status": "fresh",
                        "count": count,
                        "synced_at": last_sync.isoformat(),
                    }

        rows = build_stock_universe()
        synced_at = _utc_now_iso()

        with get_db() as conn:
            conn.execute("DELETE FROM stock_universe")
            conn.executemany(
                """
                INSERT INTO stock_universe (
                    ticker,
                    company_name,
                    normalized_name,
                    exchange,
                    exchange_code,
                    security_name,
                    security_type,
                    is_etf,
                    is_active,
                    is_searchable,
                    cik,
                    source,
                    updated_at
                ) VALUES (
                    :ticker,
                    :company_name,
                    :normalized_name,
                    :exchange,
                    :exchange_code,
                    :security_name,
                    :security_type,
                    :is_etf,
                    :is_active,
                    :is_searchable,
                    :cik,
                    :source,
                    :updated_at
                )
                """,
                rows,
            )
            conn.execute(
                """
                INSERT INTO app_meta (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (SYNC_META_KEY, synced_at, synced_at),
            )

        return {"status": "synced", "count": len(rows), "synced_at": synced_at}


def ensure_stock_universe_ready(*, stale_after_hours: int | None = None) -> dict[str, object]:
    hours = stale_after_hours if stale_after_hours is not None else _UNIVERSE_STALE_HOURS
    ensure_schema()
    with get_db() as conn:
        count_row = conn.execute("SELECT COUNT(*) AS count FROM stock_universe").fetchone()
        count = int(count_row["count"] if count_row else 0)
        last_sync = _get_last_sync_ts(conn)

    if count == 0:
        return sync_stock_universe(force=True)

    if last_sync and datetime.now(timezone.utc) - last_sync > timedelta(hours=hours):
        return sync_stock_universe(force=True)

    return {
        "status": "ready",
        "count": count,
        "synced_at": last_sync.isoformat() if last_sync else None,
    }


def search_stock_universe(query: str, *, limit: int = 20) -> list[dict[str, object]]:
    q = query.strip().upper()
    if not q:
        return []

    ensure_schema()
    ticker_exact = q
    ticker_prefix = f"{q}%"
    name_prefix = f"{q}%"
    contains = f"%{q}%"

    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT
                ticker,
                company_name,
                exchange,
                exchange_code,
                security_type,
                cik
            FROM stock_universe
            WHERE is_active = 1
              AND is_searchable = 1
              AND (
                    ticker LIKE ?
                 OR normalized_name LIKE ?
                 OR ticker LIKE ?
                 OR normalized_name LIKE ?
              )
            ORDER BY
                CASE
                    WHEN ticker = ? THEN 0
                    WHEN ticker LIKE ? THEN 1
                    WHEN normalized_name LIKE ? THEN 2
                    ELSE 3
                END,
                LENGTH(ticker),
                ticker
            LIMIT ?
            """,
            (
                ticker_prefix,
                name_prefix,
                contains,
                contains,
                ticker_exact,
                ticker_prefix,
                name_prefix,
                max(1, int(limit)),
            ),
        ).fetchall()

    return [dict(row) for row in rows]


if __name__ == "__main__":
    result = sync_stock_universe(force=True)
    print(
        f"Universe sync complete: {result['count']} rows at {result['synced_at']}"
    )
