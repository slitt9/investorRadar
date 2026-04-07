"""SEC EDGAR data fetching and CIK mapping engine.

Uses the free SEC EDGAR API to pull raw XBRL company facts
and extract fundamental financial data from 10-K/10-Q filings.
"""

import requests
from cache import cached

SEC_HEADERS = {"User-Agent": "InvestorRadarApp admin@investorradar.com"}
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


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
