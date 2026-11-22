"""Agent 1 - Universe: tickers, CIKs, and whether a company is scored yet."""
from __future__ import annotations

import yaml

from .paths import CONFIG


def load_universe() -> list[dict]:
    cfg = yaml.safe_load((CONFIG / "universe.yaml").read_text())
    out = []
    for c in cfg["companies"]:
        c = dict(c)
        c.setdefault("status", "active")
        out.append(c)
    return out


def resolve_status(companies: list[dict], facts_loader) -> list[dict]:
    """A pending company becomes active once its first 10-Q/10-K revenue is tagged."""
    for c in companies:
        if c["status"] != "pending":
            continue
        try:
            raw = facts_loader(c["cik"])
        except Exception:
            continue
        gaap = raw.get("facts", {}).get("us-gaap", {})
        for tag in ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"):
            rows = gaap.get(tag, {}).get("units", {}).get("USD", [])
            if any(r.get("form") in ("10-Q", "10-K") for r in rows):
                c["status"] = "active"
                break
    return companies
