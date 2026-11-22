"""Agent 4 - Tag-mapper: raw SEC XBRL facts -> standard items and TTM series.

Everything is point-in-time: a value is only used if it was filed on or before `asof`,
and each period is dated by the filing date of its report, not by its period end.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import yaml

from .paths import CONFIG

FORMS = {"10-K", "10-Q", "10-K/A", "10-Q/A", "10-KT", "10-QT"}


def d(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def load_tag_map() -> dict:
    return yaml.safe_load((CONFIG / "tag_map.yaml").read_text())


@dataclass
class Val:
    value: float
    accns: list = field(default_factory=list)
    tag: str = ""


class Facts:
    def __init__(self, raw: dict, tag_map: dict | None = None):
        self.gaap = raw.get("facts", {}).get("us-gaap", {})
        self.map = tag_map or load_tag_map()
        self._rows: dict[str, list] = {}

    # ---- raw access ---------------------------------------------------------
    def rows(self, tag: str) -> list[tuple]:
        """(start, end, value, filed, accession, tag) for USD facts from 10-K/10-Q filings."""
        if tag not in self._rows:
            out = []
            for r in self.gaap.get(tag, {}).get("units", {}).get("USD", []):
                if r.get("form") in FORMS and "end" in r:
                    out.append((r.get("start"), r["end"], r["val"], r["filed"], r["accn"], tag))
            self._rows[tag] = out
        return self._rows[tag]

    def _best(self, concept: str, asof: str) -> dict:
        """One row per (start, end) across ALL tags of a concept, as known on `asof`.
        The latest filing wins; on a tie the earlier tag in tag_map.yaml wins. Merging
        tags matters because a company can report a period under one tag and its
        comparatives under another."""
        best: dict = {}
        for idx, tag in enumerate(self.map["duration"][concept]):
            for s, e, v, f, a, t in self.rows(tag):
                if f > asof:
                    continue
                k = (s, e)
                if k not in best or (f, -idx) > (best[k][3], -best[k][6]):
                    best[k] = (s, e, v, f, a, t, idx)
        return best

    # ---- flows: trailing twelve months --------------------------------------
    def ttm(self, concept: str, end: str, asof: str) -> Val | None:
        best = self._best(concept, asof)
        E = d(end)
        cur = None
        for (s, e), row in best.items():
            if e == end and s is not None and (E - d(s)).days >= 80:
                if cur is None or d(s) < d(cur[0]):  # longest span = year-to-date
                    cur = row
        if cur is None:
            return None
        s0 = d(cur[0])
        dur = (E - s0).days
        if 350 <= dur <= 380:  # a full fiscal year
            return Val(cur[2], [cur[4]], cur[5])
        annual = prior = None
        for (s, e), row in best.items():
            if s is None:
                continue
            S, EE = d(s), d(e)
            ln = (EE - S).days
            if 350 <= ln <= 380 and abs((EE - (s0 - dt.timedelta(days=1))).days) <= 7:
                if annual is None or row[3] > annual[3]:
                    annual = row
            if (abs(ln - dur) <= 10 and abs((EE - (E - dt.timedelta(days=365))).days) <= 8
                    and abs((S - (s0 - dt.timedelta(days=365))).days) <= 8):
                if prior is None or row[3] > prior[3]:
                    prior = row
        if annual and prior:
            return Val(annual[2] + cur[2] - prior[2], [cur[4], annual[4], prior[4]], cur[5])
        return None

    def discrete_quarters_sum(self, concept: str, end: str, asof: str) -> float | None:
        """Second algorithm, used only by Data QA: sum the last four discrete quarters,
        where each quarter = year-to-date minus the previous year-to-date of the same
        fiscal year (a first quarter is its own year-to-date)."""
        best = self._best(concept, asof)
        cursor = d(end)
        total = 0.0
        for _ in range(4):
            ytd = None
            for (s, e), row in best.items():
                if s and d(e) == cursor and (d(e) - d(s)).days >= 80:
                    if ytd is None or d(s) < d(ytd[0]):
                        ytd = row
            if ytd is None:
                return None
            fy_start = d(ytd[0])
            if (cursor - fy_start).days <= 100:       # first quarter of its fiscal year
                total += ytd[2]
                cursor = fy_start - dt.timedelta(days=1)
                continue
            prev = None                                # YTD that ended one quarter earlier
            for (s, e), row in best.items():
                if s and abs((d(s) - fy_start).days) <= 7:
                    gap = (cursor - d(e)).days
                    if 70 <= gap <= 110 and (prev is None or abs(gap - 91) < abs((cursor - d(prev[1])).days - 91)):
                        prev = row
            if prev is None:
                return None
            total += ytd[2] - prev[2]
            cursor = d(prev[1])
        return float(total)

    # ---- balances ------------------------------------------------------------
    def instant(self, tags: list[str], end: str, asof: str) -> Val | None:
        for tag in tags:
            best = None
            for s, e, v, f, a, _t in self.rows(tag):
                if s is None and e == end and f <= asof and (best is None or f > best[3]):
                    best = (s, e, v, f, a)
            if best:
                return Val(best[2], [best[4]], tag)
        return None

    def debt(self, end: str, asof: str) -> Val | None:
        m = self.map["debt"]
        nc = self.instant(m["noncurrent"], end, asof)
        if nc is not None:
            cur = self.instant(m["current"], end, asof)
            total = nc.value + (cur.value if cur else 0.0)
            accns = nc.accns + (cur.accns if cur else [])
            src = [nc.tag] + ([cur.tag] if cur else [])
        else:
            t = self.instant(m["total"], end, asof)
            if t is None:
                return None
            total, accns, src = t.value, list(t.accns), [t.tag]
        for tag in m["short_term"]:
            st = self.instant([tag], end, asof)
            if st and st.value:
                total += st.value
                accns += st.accns
                src.append(st.tag)
        return Val(total, accns, "+".join(src))

    # ---- period ends -----------------------------------------------------------
    def period_ends(self, since: str = "2021-06-01") -> dict[str, str]:
        """{period end: filing date of the first report containing it}."""
        ends: dict[str, str] = {}
        for tag in self.map["duration"]["cfo"]:
            for s, e, v, f, a, _t in self.rows(tag):
                if s and e >= since and (d(e) - d(s)).days >= 80:
                    ends[e] = min(ends.get(e, f), f)
        return dict(sorted(ends.items()))
