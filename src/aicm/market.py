"""Agent 3 - Market: daily prices from Yahoo Finance's public chart endpoint."""
from __future__ import annotations

import datetime as dt
import time

import pandas as pd
import requests

from .paths import RAW

URL = "https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=5y&interval=1d"
HEADERS = {"User-Agent": "Mozilla/5.0 (AIMonitor educational demo)"}


def price_path(ticker: str):
    return RAW / "prices" / f"{ticker}.csv"


def fetch_prices(ticker: str, force: bool = False) -> pd.Series | None:
    p = price_path(ticker)
    if p.exists() and not force:
        return load_prices(ticker)
    p.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            r = requests.get(URL.format(t=ticker), headers=HEADERS, timeout=30)
            if r.status_code == 200:
                res = r.json()["chart"]["result"][0]
                ts = res["timestamp"]
                close = res["indicators"]["quote"][0]["close"]
                df = pd.DataFrame({"date": [dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat() for t in ts], "close": close}).dropna()
                df.to_csv(p, index=False)
                time.sleep(0.3)
                return load_prices(ticker)
        except (requests.RequestException, KeyError, TypeError, IndexError):
            pass
        time.sleep(1.5 * (attempt + 1))
    return load_prices(ticker)  # download failed: keep the last good cached prices, if any


def load_prices(ticker: str) -> pd.Series | None:
    p = price_path(ticker)
    if not p.exists():
        return None
    df = pd.read_csv(p)
    if df.empty:
        return None
    return pd.Series(df["close"].values, index=pd.to_datetime(df["date"]), name=ticker)


def drawdown(prices: pd.Series | None, asof: str | None = None) -> tuple[float | None, str | None]:
    """Drop from the 52-week high at `asof` (default: latest price)."""
    if prices is None or prices.empty:
        return None, None
    s = prices if asof is None else prices[prices.index <= pd.Timestamp(asof)]
    if s.empty:
        return None, None
    window = s[s.index > s.index[-1] - pd.Timedelta(days=365)]
    return float(1 - window.iloc[-1] / window.max()), s.index[-1].date().isoformat()
