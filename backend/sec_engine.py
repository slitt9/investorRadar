"""SEC EDGAR data fetching and CIK mapping engine.

Uses the free SEC EDGAR API to pull raw XBRL company facts
and extract fundamental financial data from 10-K/10-Q filings.
"""

import requests
from cache import cached
from bs4 import BeautifulSoup

SEC_HEADERS = {"User-Agent": "InvestorRadarApp admin@investorradar.com"}
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


@cached(ttl=86400)
def get_sec_tickers_map():
    """Fetches and returns a dict mapping TICKER -> zero-padded CIK string."""
    try:
        res = requests.get(SEC_TICKERS_URL, headers=SEC_HEADERS, timeout=15)
        data = res.json()
        return {v["ticker"]: str(v["cik_str"]).zfill(10) for v in data.values()}
    except Exception:
        return {}


@cached(ttl=86400)
def get_sec_tickers_list():
    """Returns a list of {ticker, name} dicts for search/autocomplete."""
    try:
        res = requests.get(SEC_TICKERS_URL, headers=SEC_HEADERS, timeout=15)
        data = res.json()
        return [{"ticker": v["ticker"], "name": v.get("title", "")} for v in data.values()]
    except Exception:
        return []


def _normalize_yahoo_ticker(symbol):
    # Wikipedia/NYSE uses dot notation for some tickers (e.g., BRK.B) while Yahoo uses hyphen (BRK-B).
    return (
        (symbol or "")
        .strip()
        .upper()
        .replace(".", "-")
        .replace("/", "-")
        .replace(" ", "")
    )


def _normalize_sector(sector):
    s = (sector or "").strip()
    if not s:
        return "N/A"

    # Map GICS sectors into the UI's simplified buckets.
    mapping = {
        "Information Technology": "Technology",
        "Health Care": "Healthcare",
        "Consumer Discretionary": "Consumer",
        "Consumer Staples": "Consumer",
        # Less-common buckets in the UI get grouped.
        "Communication Services": "Technology",
        "Materials": "Industrials",
        "Utilities": "Other",
        "Real Estate": "Other",
    }
    return mapping.get(s, s)


@cached(ttl=86400)
def get_sp500_constituents():
    """Returns a list of S&P 500 constituents from Wikipedia.

    Shape: [{ticker, company_name, sector, industry}]
    Ticker is normalized to Yahoo Finance format.
    """
    try:
        res = requests.get(
            SP500_WIKI_URL,
            headers={"User-Agent": SEC_HEADERS.get("User-Agent", "InvestorRadarApp")},
            timeout=20,
        )
        if res.status_code != 200:
            return []

        soup = BeautifulSoup(res.text, "html.parser")
        table = soup.find("table", {"id": "constituents"})
        if table is None:
            # Fallback: first sortable wikitable on the page.
            table = soup.select_one("table.wikitable.sortable")
        if table is None:
            return []

        header = table.find("tr")
        if header is None:
            return []

        cols = [c.get_text(" ", strip=True) for c in header.find_all(["th", "td"])]
        idx = {name: i for i, name in enumerate(cols)}

        def col_index(*names):
            for n in names:
                if n in idx:
                    return idx[n]
            return None

        sym_i = col_index("Symbol", "Ticker symbol", "Ticker")
        name_i = col_index("Security", "Company", "Name")
        sector_i = col_index("GICS Sector", "Sector")
        ind_i = col_index("GICS Sub-Industry", "Sub-Industry", "Industry")

        if sym_i is None or name_i is None:
            return []

        body = table.find("tbody") or table
        out = []
        for tr in body.find_all("tr")[1:]:
            tds = tr.find_all(["td", "th"])
            if not tds or len(tds) <= max(sym_i, name_i):
                continue

            symbol_raw = tds[sym_i].get_text(" ", strip=True)
            symbol = _normalize_yahoo_ticker(symbol_raw)
            if not symbol:
                continue

            company_name = tds[name_i].get_text(" ", strip=True) if name_i is not None else ""
            sector = (
                tds[sector_i].get_text(" ", strip=True)
                if sector_i is not None and sector_i < len(tds)
                else "N/A"
            )
            industry = tds[ind_i].get_text(" ", strip=True) if ind_i is not None and ind_i < len(tds) else "N/A"

            out.append(
                {
                    "ticker": symbol,
                    "company_name": company_name or symbol,
                    "sector": _normalize_sector(sector),
                    "industry": industry or "N/A",
                }
            )

        # De-dupe while preserving order.
        seen = set()
        deduped = []
        for row in out:
            t = row["ticker"]
            if t in seen:
                continue
            seen.add(t)
            deduped.append(row)

        return deduped
    except Exception:
        return []


def get_cik_for_ticker(ticker):
    tickers_map = get_sec_tickers_map()
    return tickers_map.get(ticker.upper())


@cached(ttl=3600)
def get_sec_facts(cik):
    """Fetches raw XBRL company facts JSON for a given CIK."""
    if not cik:
        return None
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    try:
        res = requests.get(url, headers=SEC_HEADERS, timeout=15)
        if res.status_code == 200:
            return res.json()
        return None
    except Exception:
        return None


def extract_latest_sec_fact(facts_json, tag, unit="USD"):
    """Extracts the most recently filed annual (10-K) value for a GAAP tag.

    Falls back to 10-Q if no 10-K data is available.
    """
    try:
        gaap = facts_json.get("facts", {}).get("us-gaap", {})
        if tag not in gaap:
            return None

        units = gaap[tag].get("units", {})
        if unit not in units:
            if not units:
                return None
            unit = list(units.keys())[0]

        data = units[unit]
        annual_data = [d for d in data if d.get("form") == "10-K"]
        if not annual_data:
            annual_data = [d for d in data if d.get("form") == "10-Q"]

        if not annual_data:
            return None

        latest = sorted(annual_data, key=lambda x: x.get("end", ""))[-1]
        return latest.get("val")
    except Exception:
        return None
