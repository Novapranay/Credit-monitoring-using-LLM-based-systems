"""Agent 8 - Alerts: threshold breaches, status changes and the AI-bubble lens."""
from __future__ import annotations

import pandas as pd

from .metrics import METRICS
from .scoring import LABELS, why_moved


def build_alerts(scores: pd.DataFrame, metrics: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    limit = cfg["alert_points"]
    out = []
    for t, g in scores.groupby("ticker"):
        g = g.sort_values("end")
        cur = g.iloc[-1]
        prev = g.iloc[-2] if len(g) > 1 else None
        if cur["status"] == "Not rated":
            continue
        if prev is not None and prev["status"] != "Not rated" and prev["status"] != cur["status"]:
            reasons = "; ".join(why_moved(prev, cur, cfg)) or "small changes across several metrics"
            sev = "high" if cur["status"] == "Red" else ("medium" if cur["status"] == "Amber" else "info")
            out.append({"ticker": t, "type": "Status change", "severity": sev, "period_end": cur["end"],
                        "text": f"{prev['status']} to {cur['status']} (score {prev['score']:.0f} to {cur['score']:.0f}): {reasons}"})
        for m in METRICS:
            now = cur[f"pts_{m}"]
            before = prev[f"pts_{m}"] if prev is not None else float("nan")
            if pd.isna(now) or now < limit:
                continue
            kind = "Metric breach (new)" if (not pd.isna(before) and before < limit) else "Metric breach (standing)"
            out.append({"ticker": t, "type": kind, "severity": "medium" if kind.endswith("(new)") else "info", "period_end": cur["end"],
                        "text": f"{LABELS[m]} is in the risky range ({now:.1f} of 4 risk points)"})
        if cur["triggers"]:
            for trg in cur["triggers"].split("; "):
                out.append({"ticker": t, "type": "Trigger", "severity": "high" if trg.startswith("HARD") else "medium", "period_end": cur["end"], "text": trg})
    cols = ["ticker", "type", "severity", "period_end", "text"]
    df = pd.DataFrame(out, columns=cols)
    order = {"high": 0, "medium": 1, "info": 2}
    return df.sort_values(["severity", "ticker"], key=lambda s: s.map(order) if s.name == "severity" else s).reset_index(drop=True)


def bubble_lens(metrics: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    """Latest-quarter totals across scored companies (TTM, USD)."""
    rows = []
    for t, g in metrics.groupby("ticker"):
        g = g.sort_values("end")
        cur = g.iloc[-1]
        rows.append({"ticker": t, "period_end": cur["end"], "capex": cur["capex"], "cfo": cur["cfo"], "debt": cur["debt"],
                     "prior_debt": cur["prior_debt"], "capex_to_cfo": cur["capex_to_cfo"], "net_debt": cur["net_debt"]})
    return pd.DataFrame(rows).sort_values("capex", ascending=False).reset_index(drop=True)


def bubble_summary(lens: pd.DataFrame) -> dict:
    cap, cfo = lens["capex"].sum(), lens["cfo"].sum()
    debt, prior = lens["debt"].sum(), lens["prior_debt"].sum()
    return {
        "companies": int(len(lens)), "capex": cap, "cfo": cfo, "capex_to_cfo": cap / cfo,
        "debt": debt, "prior_debt": prior, "debt_growth": debt / prior - 1 if prior else float("nan"),
        "outspending": int((lens["capex"] > lens["cfo"]).sum()),
        "outspending_names": list(lens.loc[lens["capex"] > lens["cfo"], "ticker"]),
    }


def digest_markdown(alerts: pd.DataFrame, summary: dict, scores: pd.DataFrame) -> str:
    latest = scores.sort_values("end").groupby("ticker").tail(1)
    lines = ["# Alert digest", "", "Demonstration on public SEC data. Not investment advice.", "",
             "## AI-bubble lens", "",
             f"Across {summary['companies']} scored companies, trailing-twelve-month capex is **${summary['capex']/1e9:,.0f}bn** against operating cash flow of **${summary['cfo']/1e9:,.0f}bn** ({summary['capex_to_cfo']:.0%}). "
             f"Total debt is **${summary['debt']/1e9:,.0f}bn**, up {summary['debt_growth']:.0%} year on year. "
             f"{summary['outspending']} name(s) spend more on capex than they generate in operating cash flow"
             + (": " + ", ".join(summary['outspending_names']) + "." if summary['outspending'] else "."), "",
             "## Status now", ""]
    for status in ("Red", "Amber", "Green", "Not rated"):
        names = ", ".join(latest.loc[latest["status"] == status, "ticker"])
        if names:
            lines.append(f"- **{status}**: {names}")
    for sev, title in (("high", "High severity"), ("medium", "Medium severity")):
        sub = alerts[alerts["severity"] == sev]
        if sub.empty:
            continue
        lines += ["", f"## {title}", ""]
        for _, a in sub.iterrows():
            lines.append(f"- **{a['ticker']}** ({a['type']}, period to {a['period_end']}): {a['text']}")
    standing = alerts[alerts["severity"] == "info"]
    if not standing.empty:
        lines += ["", "## Standing readings in the risky range", ""]
        for _, a in standing.iterrows():
            lines.append(f"- **{a['ticker']}**: {a['text']}")
    return "\n".join(lines) + "\n"
