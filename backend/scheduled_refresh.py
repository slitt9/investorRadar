"""Run full snapshot pipeline: optional universe sync, quotes, fundamentals.

Intended for cron / Task Scheduler (~3x per US trading day).
Environment:
  REFRESH_UNIVERSE_MODE   sp500 | mega | popular | all (default: sp500)
  REFRESH_ALL_CAP         max tickers when mode is all (default: 2500)
  SKIP_UNIVERSE_SYNC      set to 1 to skip listing sync
  FORCE_UNIVERSE_SYNC     set to 1 to force listing sync
"""

from __future__ import annotations

import os

from refresh_fundamentals import refresh_fundamentals, resolve_tickers
from refresh_quotes import refresh_quotes
from universe_sync import sync_stock_universe


def main():
    if os.environ.get("SKIP_UNIVERSE_SYNC") != "1":
        print(
            sync_stock_universe(
                force=os.environ.get("FORCE_UNIVERSE_SYNC") == "1",
            )
        )
    mode = os.environ.get("REFRESH_UNIVERSE_MODE", "sp500")
    tickers = resolve_tickers(mode)
    print(refresh_quotes(tickers))
    print(refresh_fundamentals(tickers))


if __name__ == "__main__":
    main()
