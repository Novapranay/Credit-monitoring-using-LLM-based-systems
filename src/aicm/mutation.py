"""Mutation test: corrupt good notes on purpose and count how many the Verifier catches."""
from __future__ import annotations

import copy

from .notes_common import LEVELS, NUMERIC, STATUS_PHRASE, isnan, placeholders
from .verifier import verify

SWAP = {"rose": "fell", "fell": "rose"}


def _mutations(note: dict, db: dict):
    """yield (kind, mutated_note) for each corruption that applies to this note."""
    def fresh():
        return copy.deepcopy(note)

    n = fresh(); n["sections"]["key_numbers"] += " Revenue grew 42% last year."
    yield "raw number typed", n
    n = fresh(); n["sections"]["what_changed"] += " The score is {ebitda_margin}."
    yield "unknown metric", n
    for s in ("key_numbers", "what_changed"):
        txt = note["sections"][s]
        for w, o in SWAP.items():
            if f" {w} by " in txt:
                n = fresh(); n["sections"][s] = txt.replace(f" {w} by ", f" {o} by ", 1)
                yield "flipped direction word", n
                break
        else:
            continue
        break
    n = fresh(); n["citations"] = n["citations"] + ["0000000000-26-000001"]
    yield "invented citation", n
    n = fresh(); other = next(l for l in LEVELS.values() if l != note["watch_level"]); n["watch_level"] = other
    yield "wrong watch level", n
    n = fresh(); n["sections"]["what_to_watch"] += " A buy rating looks justified."
    yield "buy/sell language", n
    n = fresh(); del n["sections"]["risks"]
    yield "missing section", n
    n = fresh(); st = db["status"]; swap = next(p for k, p in STATUS_PHRASE.items() if k != st)
    n["sections"]["headline"] = n["sections"]["headline"].replace(STATUS_PHRASE[st], swap)
    yield "wrong status phrase", n
    missing = [m for m in NUMERIC if db.get(m) is None]
    if missing:
        n = fresh(); n["sections"]["key_numbers"] += " Also {%s}." % missing[0]
        yield "value not available", n
    if db["net_debt"] > 0:
        n = fresh(); n["sections"]["key_numbers"] += " The company is in a net cash position."
        yield "false qualitative claim", n


def run(notes: dict[str, dict], claims: dict[str, dict]) -> tuple[list[dict], str]:
    rows = []
    for t, note in notes.items():
        base = verify(note, claims[t])
        for kind, mutated in _mutations(note, claims[t]):
            r = verify(mutated, claims[t])
            rows.append({"ticker": t, "mutation": kind, "caught": not r["ok"], "baseline_ok": base["ok"],
                         "reason": r["failures"][0][0] + ": " + r["failures"][0][1] if r["failures"] else ""})
    total = len(rows)
    caught = sum(r["caught"] for r in rows)
    kinds = {}
    for r in rows:
        k = kinds.setdefault(r["mutation"], [0, 0]); k[0] += 1; k[1] += r["caught"]
    lines = ["# Verifier mutation test", "",
             f"{caught} of {total} deliberately corrupted notes were rejected ({caught/total:.0%}). Every unmodified note passed first.", "",
             "| Corruption | Notes tested | Caught |", "| --- | --- | --- |"]
    for k, (n, c) in kinds.items():
        lines.append(f"| {k} | {n} | {c} |")
    missed = [r for r in rows if not r["caught"]]
    if missed:
        lines += ["", "Missed:"] + [f"- {r['ticker']}: {r['mutation']}" for r in missed]
    return rows, "\n".join(lines) + "\n"
