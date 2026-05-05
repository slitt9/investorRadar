"""CLI: sync Nasdaq/SEC listings into stock_universe."""

from __future__ import annotations

import argparse

from universe_sync import sync_stock_universe


def main():
    p = argparse.ArgumentParser(description="Refresh stock_universe from Nasdaq + SEC")
    p.add_argument("--force", action="store_true", help="Ignore freshness window")
    args = p.parse_args()
    print(sync_stock_universe(force=args.force))


if __name__ == "__main__":
    main()
