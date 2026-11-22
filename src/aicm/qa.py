"""Agent 5 - Data QA: independent cross-checks before anything is scored.

The SEC's tagged values are the filings' own numbers. QA checks that our derived
numbers are internally consistent and complete, and can stop the run.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from .tagmap import Facts, d

TIE_OUT = ("MSFT", "NVDA", "META")   # one company per fiscal-year pattern (June, January, December)
REQUIRED = ["revenue", "opinc", "cfo", "capex", "cash", "debt", "current_assets", "current_liabilities"]


def _rel(a, b):
    return abs(a - b) / abs(b) if b else np.inf


def check_company(ticker: str, facts: Facts, metrics: pd.DataFrame, newest_filing: str) -> list[dict]:
    out = []

    def add(check, status, detail):
        out.append({"ticker": ticker, "check": check, "status": status, "detail": detail})

    if metrics.empty:
        add("has_scored_period", "fail", "no period with clean revenue, cash flow, cash and debt")
        return out
    last = metrics.iloc[-1]

    # 1. freshness
    age = (d(newest_filing) - d(last["end"])).days
    add("freshness", "pass" if age <= 200 else "warn", f"latest period end {last['end']} ({age} days before the newest filing in the universe)")

    # 2. completeness of the latest period
    missing = [k for k in REQUIRED if pd.isna(last.get(k))]
    add("complete_latest", "pass" if not missing else "warn", "all items present" if not missing else "missing: " + ", ".join(missing))
    has_prior = not pd.isna(last["debt_growth_yoy"]) and not pd.isna(last["op_margin_change_yoy"])
    add("year_on_year_available", "pass" if has_prior else "warn", "prior-year period found" if has_prior else "no prior-year period; year-on-year metrics skipped")

    # 3. two independent TTM algorithms agree on the last four period ends
    worst = 0.0
    bad = []
    for _, r in metrics.tail(4).iterrows():
        for concept in ("revenue", "cfo", "opinc", "capex"):
            a = facts.ttm(concept, r["end"], r["filed"])
            b = facts.discrete_quarters_sum(concept, r["end"], r["filed"])
            if a is None or b is None:
                continue
            e = _rel(abs(a.value), abs(b)) if concept == "capex" else _rel(a.value, b)
            worst = max(worst, e)
            if e > 0.01:
                bad.append(f"{concept}@{r['end']} {e:.1%}")
    add("ttm_two_algorithms", "pass" if not bad else "fail", f"worst gap {worst:.2%} across 4 periods x 4 items" if not bad else "gap above 1%: " + "; ".join(bad))

    # 4. sanity of values
    problems = []
    if last["revenue"] <= 0: problems.append("revenue not positive")
    if last["debt"] < 0: problems.append("negative debt")
    if not pd.isna(last["capex"]) and last["capex"] < 0: problems.append("negative capex")
    cr = last["current_ratio"]
    if not pd.isna(cr) and not (0.1 < cr < 20): problems.append(f"current ratio {cr:.2f} looks wrong")
    add("sanity", "pass" if not problems else "fail", "values in plausible ranges" if not problems else "; ".join(problems))

    # 5. debt vs the reported total-debt tag, where one exists at the same period end
    alt = facts.instant(facts.map["debt"]["total"], last["end"], last["filed"])
    if alt is not None and alt.value > 0:
        e = _rel(last["debt"], alt.value)
        add("debt_vs_reported_total", "pass" if e <= 0.03 else "warn", f"our debt {last['debt']/1e9:.2f}bn vs {alt.tag} {alt.value/1e9:.2f}bn ({e:.1%} apart)")
    else:
        add("debt_vs_reported_total", "info", f"no reported total-debt tag to compare; built from {last['debt_source']}")
    # 6. cash + short-term investments vs the reported combined figure, where one exists
    comb = facts.instant(["CashCashEquivalentsAndShortTermInvestments"], last["end"], last["filed"])
    if comb is not None and comb.value > 0:
        ours = last["cash"] + last["sti"]
        e = _rel(ours, comb.value)
        add("liquid_assets_vs_reported_total", "pass" if e <= 0.03 else "warn", f"our cash + investments {ours/1e9:.1f}bn vs reported {comb.value/1e9:.1f}bn ({e:.1%} apart)")
    return out


def tie_out(facts_by_ticker: dict[str, Facts], metrics_by_ticker: dict[str, pd.DataFrame]) -> list[dict]:
    """TTM at the latest fiscal year-end vs the 10-K's own annual value (within 1%)."""
    rows = []
    for t in TIE_OUT:
        f, m = facts_by_ticker.get(t), metrics_by_ticker.get(t)
        if f is None or m is None or m.empty:
            continue
        for concept in ("revenue", "cfo"):
            best = None
            for (s, e), row in f._best(concept, "9999-12-31").items():
                if s and 350 <= (d(e) - d(s)).days <= 380 and e in set(m["end"]):
                    if best is None or e > best[1]:
                        best = (s, e, row[2])
            if best is None:
                continue
            ours = m.loc[m["end"] == best[1], concept].iloc[0]
            gap = _rel(ours, best[2])
            rows.append({"ticker": t, "item": concept, "period_end": best[1], "ours": ours, "annual_fact": best[2], "gap": gap, "status": "pass" if gap <= 0.01 else "fail"})
    return rows


def write_report(checks: list[dict], ties: list[dict], path) -> bool:
    df = pd.DataFrame(checks)
    ok = not (df["status"] == "fail").any() and all(t["status"] == "pass" for t in ties)
    lines = ["# Data QA report", "", f"Result: **{'PASS' if ok else 'FAIL'}**", "",
             "## Tie-out to the 10-K's own annual figures (TTM at the latest fiscal year-end, 1% tolerance)", "",
             "| Company | Item | Fiscal year end | Ours ($bn) | 10-K annual ($bn) | Gap | Status |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for t in ties:
        lines.append(f"| {t['ticker']} | {t['item']} | {t['period_end']} | {t['ours']/1e9:.2f} | {t['annual_fact']/1e9:.2f} | {t['gap']:.3%} | {t['status']} |")
    lines += ["", "## Checks per company", "", "| Company | Check | Status | Detail |", "| --- | --- | --- | --- |"]
    for _, r in df.iterrows():
        lines.append(f"| {r['ticker']} | {r['check']} | {r['status']} | {r['detail']} |")
    lines += ["", "Tie-outs compare against the filings' own XBRL values, not a manual read of the PDF filings. At a fiscal year-end the TTM figure is the reported annual value itself, so this confirms period selection and units, not independent accuracy; the two-algorithm check and the reported-total checks above are the independent tests."]
    path.write_text("\n".join(lines) + "\n")
    return ok
