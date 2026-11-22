"""Agent 7 - Scoring: transparent points, weights, 0-100 score, Green/Amber/Red, triggers."""
from __future__ import annotations

import math

import pandas as pd
import yaml

from .metrics import METRICS
from .paths import CONFIG

LABELS = {
    "net_debt_to_cfo": "net debt / operating cash flow",
    "capex_to_cfo": "capex / operating cash flow",
    "fcf_to_debt": "free cash flow / debt",
    "debt_growth_yoy": "debt growth (year on year)",
    "current_ratio": "current ratio",
    "op_margin_change_yoy": "operating margin change (year on year)",
    "drawdown": "share price drawdown from the one-year high",
}
WATCH = {"Green": "steady", "Amber": "keep an eye on", "Red": "worth a closer look"}


def load_config() -> dict:
    return yaml.safe_load((CONFIG / "score_config.yaml").read_text())


def band_points(value: float, bands: list[float]) -> float:
    """0..4 risk points, linear between the five band thresholds."""
    asc = bands[4] > bands[0]
    if (asc and value <= bands[0]) or (not asc and value >= bands[0]):
        return 0.0
    if (asc and value >= bands[4]) or (not asc and value <= bands[4]):
        return 4.0
    for i in range(4):
        a, b = bands[i], bands[i + 1]
        if (asc and a <= value <= b) or (not asc and b <= value <= a):
            return i + (value - a) / (b - a)
    return 4.0


def _na(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def metric_points(row: pd.Series, cfg: dict) -> dict[str, float | None]:
    """Points per metric; None = not available. Special cases for net cash and non-positive cash flow."""
    bands = cfg["bands"]
    pts: dict[str, float | None] = {}
    net_cash = row["net_debt"] <= 0
    cfo_bad = bool(row["cfo_nonpositive"])
    for m in METRICS:
        v = row[m]
        if m == "net_debt_to_cfo":
            pts[m] = 0.0 if net_cash else (4.0 if cfo_bad else (None if _na(v) else band_points(v, bands[m])))
        elif m == "capex_to_cfo":
            capex = row["capex"]
            pts[m] = None if _na(capex) else (4.0 if cfo_bad and capex > 0 else (None if _na(v) else band_points(v, bands[m])))
        elif m == "fcf_to_debt":
            if row["debt"] <= 0 or net_cash:
                pts[m] = 0.0
            else:
                pts[m] = None if _na(v) else band_points(v, bands[m])
        else:
            pts[m] = None if _na(v) else band_points(v, bands[m])
    return pts


def score_row(row: pd.Series, cfg: dict) -> dict:
    w = cfg["weights"]
    pts = metric_points(row, cfg)
    avail = {m: p for m, p in pts.items() if p is not None}
    wsum = sum(w[m] for m in avail)
    frac = wsum / sum(w.values())
    score = sum(w[m] * p / 4 for m, p in avail.items()) / wsum * 100 if wsum else math.nan
    st = cfg["status"]
    status = "Green" if score < st["green_below"] else ("Red" if score > st["red_above"] else "Amber")
    triggers = []
    trig = cfg["triggers"]
    if trig["hard_red"]["cfo_nonpositive_with_debt"] and row["cfo_nonpositive"] and row["debt"] > 0:
        triggers.append("HARD: operating cash flow is not positive while debt is outstanding")
        status = "Red"
    t = trig["watch_amber"]
    if not _na(row["capex_to_cfo"]) and row["capex_to_cfo"] > t["capex_to_cfo_above"]:
        triggers.append("WATCH: capex is above one and a half times operating cash flow")
        if status == "Green":
            status = "Amber"
    if not _na(row["debt_growth_yoy"]) and row["debt_growth_yoy"] > t["debt_growth_above"]:
        triggers.append("WATCH: debt more than doubled in a year")
        if status == "Green":
            status = "Amber"
    rated = frac >= cfg["min_weight_available"] and not math.isnan(score)
    out = {"score": round(score, 1) if rated else math.nan, "status": status if rated else "Not rated",
           "watch_level": WATCH[status] if rated else "limited data", "weight_available": round(frac, 2),
           "triggers": "; ".join(triggers)}
    for m in METRICS:
        out[f"pts_{m}"] = pts[m] if pts[m] is not None else math.nan
    return out


def score_history(metrics: pd.DataFrame, cfg: dict | None = None) -> pd.DataFrame:
    cfg = cfg or load_config()
    rows = []
    for _, r in metrics.iterrows():
        if r["end"] < cfg["history_from"]:
            continue
        s = score_row(r, cfg)
        s.update({"ticker": r["ticker"], "end": r["end"], "filed": r["filed"]})
        rows.append(s)
    return pd.DataFrame(rows)


def why_moved(prev: pd.Series, cur: pd.Series, cfg: dict, top: int = 3) -> list[str]:
    """Which metrics added or removed the most weighted risk since the prior quarter."""
    w = cfg["weights"]
    deltas = []
    for m in METRICS:
        a, b = prev[f"pts_{m}"], cur[f"pts_{m}"]
        if pd.isna(a) or pd.isna(b):
            continue
        deltas.append((w[m] * (b - a) / 4, m, a, b))
    deltas.sort(key=lambda x: -abs(x[0]))
    out = []
    for dv, m, a, b in deltas[:top]:
        if abs(dv) < 0.25:
            continue
        out.append(f"{LABELS[m]} {'added' if dv > 0 else 'removed'} {abs(dv):.1f} score points ({a:.1f} to {b:.1f} of 4 risk points)")
    return out
