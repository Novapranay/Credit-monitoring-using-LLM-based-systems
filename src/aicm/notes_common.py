"""Shared pieces of the Writer and the Verifier: the claims database and number formats."""
from __future__ import annotations

import datetime as dt
import math
import re

import pandas as pd

from .metrics import METRICS
from .scoring import LABELS, why_moved

SECTIONS = ["headline", "what_changed", "key_numbers", "risks", "what_to_watch"]
PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")
STATUS_PHRASE = {"Green": "on solid footing", "Amber": "stretched in places", "Red": "under pressure"}
LEVELS = {"Green": "steady", "Amber": "keep an eye on", "Red": "worth a closer look"}
UP = {"rose", "increased", "grew", "climbed", "expanded", "widened", "higher"}
DOWN = {"fell", "decreased", "declined", "dropped", "shrank", "contracted", "narrowed", "lower"}
ADVICE = re.compile(r"\b(buy|sell|hold rating|price target|outperform|underperform|overweight|underweight|recommend\w*)\b", re.I)

# numeric placeholders and how their value is printed; signed ones print a magnitude and need a direction word
NUMERIC = {
    "net_debt_to_cfo": lambda v: f"{v:.1f} years",
    "capex_to_cfo": lambda v: f"{v:.0%}",
    "fcf_to_debt": lambda v: f"{v:.0%}",
    "debt_growth_yoy": lambda v: f"{abs(v):.0%}",
    "current_ratio": lambda v: f"{v:.2f}x",
    "op_margin_change_yoy": lambda v: f"{abs(v) * 100:.1f} percentage points",
    "drawdown": lambda v: f"{v:.0%}",
    "score": lambda v: f"{v:.0f} out of 100",
    "score_change": lambda v: f"{abs(v):.0f} points",
}
SIGNED = {"debt_growth_yoy", "op_margin_change_yoy", "score_change"}
TEXT = {"name", "ticker", "status", "prev_status", "driver", "risk_list", "trigger_list", "period_end"}


def nice_date(iso: str) -> str:
    d = dt.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b %Y')}"


def isnan(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def build_claims(ticker: str, name: str, metrics: pd.DataFrame, scores: pd.DataFrame, cfg: dict) -> dict | None:
    """Everything a note may cite, taken from the computed tables. Returns None if not scored."""
    m = metrics[metrics["ticker"] == ticker].sort_values("end")
    s = scores[scores["ticker"] == ticker].sort_values("end")
    if m.empty or s.empty or s.iloc[-1]["status"] == "Not rated":
        return None
    cur_m, cur_s = m.iloc[-1], s.iloc[-1]
    prev_s = s.iloc[-2] if len(s) > 1 and s.iloc[-2]["status"] != "Not rated" else None
    db = {k: (None if isnan(cur_m[k]) else float(cur_m[k])) for k in METRICS}
    db["score"] = float(cur_s["score"])
    db["score_change"] = float(cur_s["score"] - prev_s["score"]) if prev_s is not None else None
    db.update({"name": name, "ticker": ticker, "status": cur_s["status"], "prev_status": prev_s["status"] if prev_s is not None else None,
               "period_end": nice_date(cur_m["end"]), "period_end_iso": cur_m["end"], "net_debt": float(cur_m["net_debt"]),
               "cfo_nonpositive": bool(cur_m["cfo_nonpositive"])})
    why = why_moved(prev_s, cur_s, cfg, top=1) if prev_s is not None else []
    db["driver"] = next((LABELS[k] for k in METRICS if why and why[0].startswith(LABELS[k])), "no single metric")
    risky = [LABELS[k] for k in METRICS if not isnan(cur_s[f"pts_{k}"]) and cur_s[f"pts_{k}"] >= cfg["alert_points"]]
    db["risk_list"] = "; ".join(risky) if risky else "none"
    trig = [t.split(": ", 1)[1] for t in cur_s["triggers"].split("; ") if t]
    db["trigger_list"] = "; ".join(trig) if trig else "none"
    db["accns"] = [a for a in str(cur_m["accns"]).split(";") if a]
    db["cik_for_links"] = None
    return db


def fmt_value(name: str, db: dict) -> str:
    v = db[name]
    if name in NUMERIC:
        return NUMERIC[name](v)
    return str(v)


def placeholders(text: str) -> list[str]:
    return PLACEHOLDER.findall(text)


def render(text: str, db: dict) -> str:
    return PLACEHOLDER.sub(lambda mo: fmt_value(mo.group(1), db), text)
