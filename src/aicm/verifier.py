"""Agent 10 - Verifier: six checks on every note; numbers are filled in only after a pass."""
from __future__ import annotations

import re

from .notes_common import (ADVICE, DOWN, LEVELS, NUMERIC, PLACEHOLDER, SECTIONS, SIGNED, STATUS_PHRASE, TEXT, UP,
                           isnan, placeholders, render)

SENT = re.compile(r"(?<=[.!?])\s+")
CHECKS = ["1 no raw digits", "2 placeholders valid", "3 direction and claims", "4 citations", "5 level, status and tone", "6 template"]


def _text_without_placeholders(t: str) -> str:
    return PLACEHOLDER.sub("", t)


def verify(note: dict, db: dict) -> dict:
    """Returns {"ok": bool, "failures": [(check, detail)], "rendered": {section: text}}."""
    fails: list[tuple[str, str]] = []
    sec = note.get("sections", {})

    # 6 template: five sections, each non-empty
    for s in SECTIONS:
        if not str(sec.get(s, "")).strip():
            fails.append((CHECKS[5], f"section '{s}' missing or empty"))
    full = " ".join(str(sec.get(s, "")) for s in SECTIONS)

    # 1 no raw digits outside placeholders
    if re.search(r"\d", _text_without_placeholders(full)):
        fails.append((CHECKS[0], "digit typed by the writer outside a placeholder"))

    # 2 every placeholder names a known item that has a value for this company
    for name in placeholders(full):
        if name not in NUMERIC and name not in TEXT:
            fails.append((CHECKS[1], f"unknown placeholder {{{name}}}"))
        elif db.get(name) is None:
            fails.append((CHECKS[1], f"{{{name}}} has no value for {db['ticker']}"))

    # 3 direction words agree with the sign; qualitative claims agree with the data
    for s in SECTIONS:
        for sentence in SENT.split(str(sec.get(s, ""))):
            signed = [n for n in placeholders(sentence) if n in SIGNED and db.get(n) is not None]
            if not signed:
                continue
            words = set(re.findall(r"[a-z]+", sentence.lower()))
            up, down = bool(words & UP), bool(words & DOWN)
            for n in signed:
                v = db[n]
                if (up and down) or (up and v < 0) or (down and v > 0):
                    fails.append((CHECKS[2], f"direction word contradicts the sign of {{{n}}}"))
                elif not up and not down:
                    fails.append((CHECKS[2], f"no direction word next to signed {{{n}}}"))
    low = full.lower()
    if "net cash position" in low and db["net_debt"] > 0:
        fails.append((CHECKS[2], "claims a net cash position but net debt is positive"))
    if "no metric is currently in the risky range" in low and db["risk_list"] != "none":
        fails.append((CHECKS[2], "claims no risky metric but some are in the risky range"))
    if "operating cash flow is not positive" in low and not db["cfo_nonpositive"]:
        fails.append((CHECKS[2], "claims non-positive operating cash flow but it is positive"))

    # 4 citations must be filings actually used for this company's numbers
    cites = note.get("citations", [])
    if not cites:
        fails.append((CHECKS[3], "no citations"))
    for a in cites:
        if a not in db["accns"]:
            fails.append((CHECKS[3], f"citation {a} is not a filing used for {db['ticker']}"))

    # 5 watch level and status phrase match the rules; no advice language
    want = LEVELS[db["status"]]
    if note.get("watch_level") != want:
        fails.append((CHECKS[4], f"declared watch level '{note.get('watch_level')}' differs from rules level '{want}'"))
    wtw = str(sec.get("what_to_watch", "")).lower()
    if want not in wtw or any(l in wtw for l in LEVELS.values() if l != want and l not in want):
        fails.append((CHECKS[4], "what_to_watch does not state the rules level"))
    head = str(sec.get("headline", "")).lower()
    if STATUS_PHRASE[db["status"]] not in head or any(p in head for st, p in STATUS_PHRASE.items() if st != db["status"]):
        fails.append((CHECKS[4], "headline does not match the status"))
    if ADVICE.search(full):
        fails.append((CHECKS[4], "buy/sell/advice language"))

    rendered = {}
    if not fails:
        rendered = {s: render(str(sec[s]), db) for s in SECTIONS}
    return {"ok": not fails, "failures": fails, "rendered": rendered}
