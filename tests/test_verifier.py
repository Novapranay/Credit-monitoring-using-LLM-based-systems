import copy

from aicm import mutation
from aicm.notes_common import LEVELS, SECTIONS
from aicm.verifier import verify
from aicm.writer import template_note

DB = dict(name="Acme", ticker="ACME", status="Amber", prev_status="Green", period_end="30 Sep 2026", period_end_iso="2026-09-30",
          net_debt=50.0, cfo_nonpositive=False, net_debt_to_cfo=2.0, capex_to_cfo=1.2, fcf_to_debt=-0.1, debt_growth_yoy=0.5,
          current_ratio=1.1, op_margin_change_yoy=-0.03, drawdown=0.2, score=40.0, score_change=12.0, driver="capex / operating cash flow",
          risk_list="capex / operating cash flow", trigger_list="none", accns=["0000000001-26-000001"])


def test_template_note_passes_all_checks_and_fills_numbers():
    note = template_note(DB)
    r = verify(note, DB)
    assert r["ok"], r["failures"]
    assert "120%" in r["rendered"]["key_numbers"] or "1.2" in r["rendered"]["key_numbers"] or "120" in r["rendered"]["key_numbers"]
    assert "fell by 3.0 percentage points" in r["rendered"]["key_numbers"]


def test_writer_text_has_no_digits():
    note = template_note(DB)
    import re
    from aicm.notes_common import PLACEHOLDER
    for s in SECTIONS:
        assert not re.search(r"\d", PLACEHOLDER.sub("", note["sections"][s]))


def test_every_mutation_is_caught():
    note = template_note(DB)
    assert verify(note, DB)["ok"]
    rows, _ = mutation.run({"ACME": note}, {"ACME": DB})
    assert rows and all(r["caught"] for r in rows), [r for r in rows if not r["caught"]]


def test_flipped_direction_is_caught_specifically():
    note = template_note(DB)
    bad = copy.deepcopy(note)
    bad["sections"]["key_numbers"] = bad["sections"]["key_numbers"].replace("Debt rose by", "Debt fell by")
    r = verify(bad, DB)
    assert not r["ok"] and any("direction" in d for _, d in r["failures"])
