"""Agent 9 - Writer: drafts a credit note as prose with placeholders. It never types a number.

Default: a deterministic template writer (free, reproducible). With AICM_USE_LLM=1 and
ANTHROPIC_API_KEY set, an LLM drafts the prose under the same placeholder rules; the
Verifier checks both identically.
"""
from __future__ import annotations

import hashlib
import json
import os

from .notes_common import LEVELS, NUMERIC, SECTIONS, SIGNED, STATUS_PHRASE, TEXT, isnan
from .paths import DATA


def _dir(v: float) -> str:
    return "rose" if v > 0 else "fell"


def template_note(db: dict) -> dict:
    status = db["status"]
    sec: dict[str, str] = {}
    sec["headline"] = f"{{name}} is {STATUS_PHRASE[status]}: risk score {{score}}."

    # what changed
    parts = []
    ch = db["score_change"]
    if ch is None:
        parts.append("This is the first period with a full set of data, so there is no prior quarter to compare.")
    else:
        if abs(ch) < 0.5:
            parts.append("Its risk score was little changed from the prior quarter, at {score} for the period ended {period_end}.")
        else:
            parts.append(f"Its risk score {_dir(ch)} by {{score_change}} from the prior quarter, to {{score}} for the period ended {{period_end}}.")
        if db["prev_status"] and db["prev_status"] != status:
            parts.append("Its status moved from {prev_status} to {status}; the largest driver was {driver}.")
        else:
            parts.append("Its status is unchanged at {status}.")
    sec["what_changed"] = " ".join(parts)

    # key numbers, each with a short reason it matters
    k = []
    if db["net_debt"] <= 0:
        k.append("Cash and short-term investments exceed debt, so the company is in a net cash position.")
    elif db["cfo_nonpositive"]:
        k.append("Operating cash flow is not positive, so borrowings cannot be repaid from operations.")
    elif db["net_debt_to_cfo"] is not None:
        k.append("Net debt equals {net_debt_to_cfo} of operating cash flow, a measure of how long operations would take to repay borrowings.")
    if db["capex_to_cfo"] is not None:
        k.append("Capital spending absorbs {capex_to_cfo} of operating cash flow; a figure above full coverage means the buildout is funded from reserves or new borrowing.")
    if db["fcf_to_debt"] is not None:
        k.append("Free cash flow is {fcf_to_debt} of total debt.")
    if db["debt_growth_yoy"] is not None:
        k.append(f"Debt {_dir(db['debt_growth_yoy'])} by {{debt_growth_yoy}} over the past year.")
    if db["current_ratio"] is not None:
        k.append("The current ratio is {current_ratio}, a gauge of short-term liquidity.")
    if db["op_margin_change_yoy"] is not None:
        k.append(f"Operating margin {_dir(db['op_margin_change_yoy'])} by {{op_margin_change_yoy}} year on year.")
    if db["drawdown"] is not None:
        k.append("The share price sits {drawdown} below its one-year high.")
    sec["key_numbers"] = " ".join(k)

    # risks
    r = []
    if db["risk_list"] == "none":
        r.append("No metric is currently in the risky range.")
    else:
        r.append("The weakest readings are {risk_list}.")
    if db["trigger_list"] != "none":
        r.append("Active triggers: {trigger_list}.")
    r.append("Reported debt excludes off-balance-sheet financing such as data-centre joint ventures, so leverage may be understated.")
    sec["risks"] = " ".join(r)

    sec["what_to_watch"] = f"Watch level: {LEVELS[status]}. The next check is the following quarterly filing. This is a screening note on public data, not investment advice."
    return {"ticker": db["ticker"], "writer": "template", "sections": sec, "watch_level": LEVELS[status], "citations": list(db["accns"])}


# ---------------------------------------------------------------- optional LLM writer
SYSTEM = """You write short credit notes for finance readers. Rules, all enforced by a verifier:
1. NEVER type a digit. Refer to numbers only through placeholders like {capex_to_cfo}.
2. Allowed placeholders: %s.
3. Placeholders marked signed print a magnitude: write a direction word (rose, fell, increased, declined...) matching the sign given in the facts.
4. Reply with JSON only: {"sections": {"headline","what_changed","key_numbers","risks","what_to_watch"}, "watch_level": "<given level>"}.
5. No buy, sell, hold or price-target language. The watch level is given; state it in what_to_watch.
6. Headline must contain the given status phrase."""


def llm_note(db: dict) -> dict:
    import anthropic  # optional dependency

    allowed = ", ".join("{%s}" % n for n in list(NUMERIC) + sorted(TEXT))
    sheet = {
        "ticker": db["ticker"], "status": db["status"], "status_phrase": STATUS_PHRASE[db["status"]], "watch_level": LEVELS[db["status"]],
        "available_numeric_placeholders": {n: ("signed, value is %s" % ("positive" if (db.get(n) or 0) > 0 else "negative") if n in SIGNED else "magnitude") for n in NUMERIC if db.get(n) is not None},
        "net_cash": db["net_debt"] <= 0, "risk_list": db["risk_list"], "trigger_list": db["trigger_list"], "has_prior_quarter": db["score_change"] is not None,
    }
    key = hashlib.sha256(json.dumps(sheet, sort_keys=True).encode()).hexdigest()[:16]
    cache = DATA / "llm_cache" / f"{key}.json"
    if cache.exists():
        body = json.loads(cache.read_text())
    else:
        client = anthropic.Anthropic()
        msg = client.messages.create(model=os.getenv("AICM_MODEL", "claude-sonnet-5-5"), max_tokens=1200, system=SYSTEM % allowed,
                                     messages=[{"role": "user", "content": json.dumps(sheet)}])
        text = msg.content[0].text.strip().removeprefix("```json").removesuffix("```").strip()
        body = json.loads(text)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(body))
    return {"ticker": db["ticker"], "writer": "llm", "sections": {k: body["sections"].get(k, "") for k in SECTIONS},
            "watch_level": body.get("watch_level", ""), "citations": list(db["accns"])}


def write_note(db: dict) -> dict:
    if os.getenv("AICM_USE_LLM") == "1" and os.getenv("ANTHROPIC_API_KEY"):
        return llm_note(db)
    return template_note(db)
