"""Agent 11 - Publisher: writes the watchlist, alert digest and verified notes."""
from __future__ import annotations

import pandas as pd

from .alerts import digest_markdown
from .metrics import METRICS
from .notes_common import SECTIONS, nice_date
from .paths import OUTPUT, PROCESSED

STATUS_ORDER = {"Red": 0, "Amber": 1, "Green": 2, "Not rated": 3, "Pending first 10-Q": 4}
DISCLAIMER = "Demonstration on public SEC and market data. Not investment advice."


def sec_link(cik: int, accn: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn.replace('-', '')}/"


def note_markdown(company: dict, note: dict, result: dict, db: dict) -> str:
    ok = result["ok"]
    sec = result["rendered"]
    lines = [f"# {company['name']} ({company['ticker']}): credit note", ""]
    if not ok:
        lines += ["> **NEEDS REVIEW. This note failed verification and is not published.**", ""]
        lines += [f"> - check {c}: {d}" for c, d in result["failures"]]
        return "\n".join(lines) + "\n"
    lines += [f"**{sec['headline']}**", "", f"*Period ended {db['period_end']}. Status: {db['status']}.*", ""]
    titles = {"what_changed": "What changed", "key_numbers": "Key numbers explained", "risks": "Risks", "what_to_watch": "What to watch"}
    for k in ("what_changed", "key_numbers", "risks", "what_to_watch"):
        lines += [f"## {titles[k]}", "", sec[k], ""]
    lines += ["## Sources", ""]
    lines += [f"- SEC filing {a}: {sec_link(company['cik'], a)}" for a in note["citations"]]
    lines += ["- Prices: Yahoo Finance daily closes", "",
              f"*Verified: all six checks passed. Numbers were filled in by code from the computed data (writer: {note['writer']}). {DISCLAIMER}*"]
    return "\n".join(lines) + "\n"


def watchlist(companies: list[dict], metrics: pd.DataFrame, scores: pd.DataFrame, alerts: pd.DataFrame, note_ok: dict[str, bool]) -> pd.DataFrame:
    rows = []
    latest_m = metrics.sort_values("end").groupby("ticker").tail(1).set_index("ticker")
    ss = scores.sort_values("end")
    for c in companies:
        t = c["ticker"]
        base = {"ticker": t, "name": c["name"], "layer": c["layer"], "angle": c["angle"]}
        if c["status"] == "pending" or t not in latest_m.index:
            rows.append({**base, "status": "Pending first 10-Q", "watch_level": "wait for the first quarterly report", "note": "pending"})
            continue
        g = ss[ss["ticker"] == t]
        cur, prev = g.iloc[-1], (g.iloc[-2] if len(g) > 1 else None)
        m = latest_m.loc[t]
        top = alerts[(alerts["ticker"] == t) & (alerts["severity"].isin(["high", "medium"]))]
        rows.append({**base, "status": cur["status"], "score": cur["score"],
                     "score_change": (cur["score"] - prev["score"]) if prev is not None and prev["status"] != "Not rated" else float("nan"),
                     "watch_level": cur["watch_level"], "period_end": m["end"], "filed": m["filed"],
                     **{k: m[k] for k in METRICS}, "net_debt": m["net_debt"], "capex": m["capex"], "cfo": m["cfo"], "debt": m["debt"],
                     "top_alert": top.iloc[0]["text"] if not top.empty else "", "triggers": cur["triggers"],
                     "note": "published" if note_ok.get(t) else "needs review"})
    df = pd.DataFrame(rows)
    df["_o"] = df["status"].map(STATUS_ORDER)
    return df.sort_values(["_o", "score"], ascending=[True, False]).drop(columns="_o").reset_index(drop=True)


def publish(companies, metrics, scores, alerts, lens, summary, watch, notes_md: dict[str, tuple[str, bool]]):
    OUTPUT.mkdir(exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "notes").mkdir(exist_ok=True)
    (OUTPUT / "needs_review").mkdir(exist_ok=True)
    metrics.to_csv(PROCESSED / "metrics.csv", index=False)
    scores.to_csv(PROCESSED / "scores.csv", index=False)
    alerts.to_csv(PROCESSED / "alerts.csv", index=False)
    lens.to_csv(PROCESSED / "bubble_lens.csv", index=False)
    pd.Series(summary).to_json(PROCESSED / "bubble_summary.json")
    watch.to_csv(OUTPUT / "watchlist.csv", index=False)
    (OUTPUT / "alerts.md").write_text(digest_markdown(alerts, summary, scores))
    for t, (md, ok) in notes_md.items():
        (OUTPUT / ("notes" if ok else "needs_review") / f"{t}.md").write_text(md)
