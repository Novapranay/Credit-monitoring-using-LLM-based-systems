"""Orchestrator (agent 0): runs the five stages in order, stops at a failed gate, logs each run.

    python run.py              # use cached data where present
    python run.py --refresh    # re-download SEC facts and prices
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd

from aicm import alerts as alerts_agent, filings, market, mutation, publisher, qa, universe
from aicm.metrics import company_metrics
from aicm.notes_common import build_claims
from aicm.paths import OUTPUT
from aicm.scoring import load_config, score_history
from aicm.tagmap import Facts
from aicm.verifier import verify
from aicm.writer import write_note

log: list[dict] = []


def step(agent: str, **info):
    log.append({"agent": agent, "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), **info})
    print(f"[{agent}] " + ", ".join(f"{k}={v}" for k, v in info.items()))


def gate(name: str, ok: bool, detail: str = ""):
    step("gate", name=name, passed=ok, detail=detail)
    if not ok:
        OUTPUT.mkdir(exist_ok=True)
        (OUTPUT / "run_log.json").write_text(json.dumps(log, indent=2))
        sys.exit(f"Gate failed: {name}. {detail}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-download SEC facts and prices")
    ap.add_argument("--require-prices", action="store_true", help="stop if any active company has no price data (used by the scheduled job)")
    args = ap.parse_args()
    t0 = time.time()
    cfg = load_config()

    # Stage 1: ingest
    companies = universe.load_universe()
    step("universe", companies=len(companies))
    errors = filings.fetch_all(companies, force=args.refresh)
    universe.resolve_status(companies, filings.load_facts)
    active = [c for c in companies if c["status"] == "active"]
    step("filings", downloaded=len(companies) - len(errors), errors=len(errors))
    no_price = []
    prices = {}
    for c in companies:
        prices[c["ticker"]] = market.fetch_prices(c["ticker"], force=args.refresh)
        if prices[c["ticker"]] is None:
            no_price.append(c["ticker"])
    step("market", with_prices=len(companies) - len(no_price), without=",".join(no_price) or "none")
    if args.require_prices:
        gate("all active companies have price data", not [c["ticker"] for c in active if c["ticker"] in no_price], ",".join(no_price))
    gate("all active companies have SEC data", not [c["ticker"] for c in active if c["ticker"] in errors], str(errors))

    # Stage 2: normalise and check
    facts = {c["ticker"]: Facts(filings.load_facts(c["cik"])) for c in active}
    metrics_by = {c["ticker"]: company_metrics(c["ticker"], facts[c["ticker"]], prices[c["ticker"]]) for c in active}
    step("tag-mapper", periods={t: len(m) for t, m in metrics_by.items()})
    newest = max(m["filed"].max() for m in metrics_by.values() if not m.empty)
    checks = [r for c in active for r in qa.check_company(c["ticker"], facts[c["ticker"]], metrics_by[c["ticker"]], newest)]
    ties = qa.tie_out(facts, metrics_by)
    OUTPUT.mkdir(exist_ok=True)
    qa_ok = qa.write_report(checks, ties, OUTPUT / "qa_report.md")
    gate("data QA passes", qa_ok, "see output/qa_report.md")

    # Stage 3: analyse
    metrics = pd.concat([m for m in metrics_by.values() if not m.empty], ignore_index=True)
    scores = pd.concat([score_history(m, cfg) for m in metrics_by.values() if not m.empty], ignore_index=True)
    step("metrics", rows=len(metrics))
    step("scoring", rows=len(scores))
    alert_df = alerts_agent.build_alerts(scores, metrics, cfg)
    lens = alerts_agent.bubble_lens(metrics, scores)
    summary = alerts_agent.bubble_summary(lens)
    step("alerts", alerts=len(alert_df), outspending=summary["outspending"])

    # Stage 4: write and verify
    claims, notes, results = {}, {}, {}
    for c in active:
        db = build_claims(c["ticker"], c["name"], metrics, scores, cfg)
        if db is None:
            continue
        claims[c["ticker"]] = db
        notes[c["ticker"]] = write_note(db)
        results[c["ticker"]] = verify(notes[c["ticker"]], db)
    passed = sum(r["ok"] for r in results.values())
    step("writer+verifier", notes=len(notes), verified=passed, needs_review=len(notes) - passed)
    _, report = mutation.run(notes, claims)
    (OUTPUT / "mutation_report.md").write_text(report)
    step("mutation-test", report="output/mutation_report.md")

    # Stage 5: publish (only verified notes are published)
    note_ok = {t: r["ok"] for t, r in results.items()}
    watch = publisher.watchlist(companies, metrics, scores, alert_df, note_ok)
    by = {c["ticker"]: c for c in companies}
    notes_md = {t: (publisher.note_markdown(by[t], notes[t], results[t], claims[t]), results[t]["ok"]) for t in notes}
    publisher.publish(companies, metrics, scores, alert_df, lens, summary, watch, notes_md)
    step("publisher", watchlist=len(watch), seconds=round(time.time() - t0, 1))
    (OUTPUT / "run_log.json").write_text(json.dumps(log, indent=2))
    # Small committed marker the dashboard shows as "Last updated".
    price_dates = [d for d in metrics["price_date"].dropna().unique()] if "price_date" in metrics else []
    (OUTPUT / "last_run.json").write_text(json.dumps({
        "finished_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "downloaded_fresh_data": bool(args.refresh),
        "newest_filing": str(newest),
        "latest_price_date": str(max(price_dates)) if price_dates else None,
        "seconds": round(time.time() - t0, 1),
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
