"""SQLite helpers for local screener datasets."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def get_database_path() -> Path:
    raw = os.environ.get("INVESTOR_RADAR_DB_PATH")
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path(__file__).resolve().parent / "data" / "investorradar.db").resolve()


def _connect() -> sqlite3.Connection:
    db_path = get_database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


@contextmanager
def get_db():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def ensure_schema() -> None:
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS stock_universe (
                ticker TEXT PRIMARY KEY,
                company_name TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                exchange TEXT,
                exchange_code TEXT,
                security_name TEXT NOT NULL,
                security_type TEXT NOT NULL,
                is_etf INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                is_searchable INTEGER NOT NULL DEFAULT 1,
                cik TEXT,
                source TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_stock_universe_name
                ON stock_universe(normalized_name);

            CREATE INDEX IF NOT EXISTS idx_stock_universe_searchable
                ON stock_universe(is_searchable, is_active, ticker);

            CREATE INDEX IF NOT EXISTS idx_stock_universe_exchange
                ON stock_universe(exchange_code, is_active);
            """
        )

