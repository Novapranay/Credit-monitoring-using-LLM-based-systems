"""Agent 2 - Filings: downloads SEC company facts (cached, rate-limited)."""
from __future__ import annotations

import json
import os
import time

import requests

from .paths import RAW

UA = os.getenv("SEC_USER_AGENT", "AIMonitor/0.1 educational-demo (set SEC_USER_AGENT to your contact)")
URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"


def cache_path(cik: int):
    return RAW / "facts" / f"CIK{cik:010d}.json"


def fetch_facts(cik: int, force: bool = False) -> dict:
    p = cache_path(cik)
    if p.exists() and not force:
        return json.loads(p.read_text())
    p.parent.mkdir(parents=True, exist_ok=True)
    last = None
    for attempt in range(4):
        try:
            r = requests.get(URL.format(cik=cik), headers={"User-Agent": UA}, timeout=60)
            if r.status_code == 200:
                p.write_bytes(r.content)
                time.sleep(0.2)  # stay well under SEC's fair-access limit
                return r.json()
            last = f"HTTP {r.status_code}"
        except requests.RequestException as e:  # network hiccup: back off and retry
            last = str(e)
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"SEC download failed for CIK {cik}: {last}")


def load_facts(cik: int) -> dict:
    return json.loads(cache_path(cik).read_text())


def fetch_all(companies: list[dict], force: bool = False) -> dict[str, str]:
    """Returns {ticker: error} for downloads that failed."""
    errors = {}
    for c in companies:
        try:
            fetch_facts(c["cik"], force=force)
        except Exception as e:
            errors[c["ticker"]] = str(e)
    return errors
