"""Agent 6 - Metrics: the seven credit ratios, per quarter, point-in-time."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from .market import drawdown
from .tagmap import Facts, d

METRICS = ["net_debt_to_cfo", "capex_to_cfo", "fcf_to_debt", "debt_growth_yoy",
           "current_ratio", "op_margin_change_yoy", "drawdown"]


def raw_rows(facts: Facts) -> list[dict]:
    """Standard items for every fiscal period end, using only data filed by each report."""
    rows = []
    for end, filed in facts.period_ends().items():
        rev = facts.ttm("revenue", end, filed)
        opi = facts.ttm("opinc", end, filed)
        cfo = facts.ttm("cfo", end, filed)
        cap = facts.ttm("capex", end, filed)
        cash = facts.instant(facts.map["instant"]["cash"], end, filed)
        sti = facts.instant(facts.map["instant"]["sti"], end, filed)
        ca = facts.instant(facts.map["instant"]["current_assets"], end, filed)
        cl = facts.instant(facts.map["instant"]["current_liabilities"], end, filed)
        debt = facts.debt(end, filed)
        if rev is None or cfo is None or cash is None or debt is None:
            continue  # not enough clean data for this period
        used = [v for v in (rev, opi, cfo, cap, cash, sti, ca, cl, debt) if v is not None]
        rows.append({
            "end": end, "filed": filed,
            "revenue": rev.value, "opinc": opi.value if opi else np.nan,
            "cfo": cfo.value, "capex": abs(cap.value) if cap else np.nan,
            "cash": cash.value, "sti": sti.value if sti else 0.0,
            "current_assets": ca.value if ca else np.nan,
            "current_liabilities": cl.value if cl else np.nan,
            "debt": debt.value, "debt_source": debt.tag,
            "accns": sorted({a for v in used for a in v.accns}),
        })
    return rows


def _prior(rows: list[dict], end: str) -> dict | None:
    target = d(end) - dt.timedelta(days=365)
    best = None
    for r in rows:
        gap = abs((d(r["end"]) - target).days)
        if gap <= 12 and (best is None or gap < best[0]):
            best = (gap, r)
    return best[1] if best else None


def company_metrics(ticker: str, facts: Facts, prices: pd.Series | None, since: str = "2022-06-01") -> pd.DataFrame:
    rows = raw_rows(facts)
    out = []
    for i, r in enumerate(rows):
        if r["end"] < since:
            continue
        p = _prior(rows, r["end"])
        net_debt = r["debt"] - r["cash"] - r["sti"]
        cfo_pos = r["cfo"] > 0
        m = dict(r)
        m["ticker"] = ticker
        m["net_debt"] = net_debt
        m["cfo_nonpositive"] = not cfo_pos
        m["net_debt_to_cfo"] = net_debt / r["cfo"] if cfo_pos else np.nan
        m["capex_to_cfo"] = r["capex"] / r["cfo"] if cfo_pos and not np.isnan(r["capex"]) else np.nan
        m["fcf_to_debt"] = (r["cfo"] - r["capex"]) / r["debt"] if r["debt"] > 0 and not np.isnan(r["capex"]) else np.nan
        pdebt = p["debt"] if p else np.nan
        m["prior_debt"] = pdebt
        m["debt_growth_yoy"] = r["debt"] / pdebt - 1 if p and pdebt > 0 else np.nan
        cl = r["current_liabilities"]
        m["current_ratio"] = r["current_assets"] / cl if cl and not np.isnan(cl) and cl > 0 else np.nan
        margin = r["opinc"] / r["revenue"] if r["revenue"] and not np.isnan(r["opinc"]) else np.nan
        pmargin = p["opinc"] / p["revenue"] if p and p["revenue"] and not np.isnan(p["opinc"]) else np.nan
        m["op_margin"] = margin
        m["op_margin_change_yoy"] = margin - pmargin if not (np.isnan(margin) or np.isnan(pmargin)) else np.nan
        dd, pdate = drawdown(prices, r["filed"])
        m["drawdown"] = dd if dd is not None else np.nan
        m["price_date"] = pdate
        out.append(m)
    df = pd.DataFrame(out)
    if df.empty:
        return df
    # the latest period is priced as of the latest available close, not its filing date
    dd, pdate = drawdown(prices)
    if dd is not None:
        df.loc[df.index[-1], "drawdown"] = dd
        df.loc[df.index[-1], "price_date"] = pdate
    df["accns"] = df["accns"].apply(lambda x: ";".join(x))
    return df
