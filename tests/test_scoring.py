import math

import pandas as pd

from aicm.scoring import band_points, load_config, score_row


def row(**kw):
    base = dict(net_debt=-5.0, debt=10.0, cfo_nonpositive=False, capex=1.0, net_debt_to_cfo=-0.1, capex_to_cfo=0.2, fcf_to_debt=1.0,
                debt_growth_yoy=0.0, current_ratio=2.0, op_margin_change_yoy=0.01, drawdown=0.05)
    base.update(kw)
    return pd.Series(base)


def test_band_points_rising_and_falling():
    assert band_points(0.5, [1, 2, 3, 4, 5]) == 0
    assert band_points(9, [1, 2, 3, 4, 5]) == 4
    assert band_points(2.5, [1, 2, 3, 4, 5]) == 1.5
    assert band_points(1.5, [1.5, 1.25, 1.0, 0.9, 0.8]) == 0
    assert band_points(0.8, [1.5, 1.25, 1.0, 0.9, 0.8]) == 4


def test_healthy_company_is_green():
    s = score_row(row(), load_config())
    assert s["status"] == "Green" and s["score"] < 10


def test_hard_trigger_forces_red():
    s = score_row(row(cfo_nonpositive=True, net_debt=5.0, net_debt_to_cfo=math.nan, capex_to_cfo=math.nan), load_config())
    assert s["status"] == "Red" and "HARD" in s["triggers"]


def test_watch_trigger_forces_at_least_amber():
    s = score_row(row(debt_growth_yoy=1.5), load_config())
    assert s["status"] == "Amber" and "WATCH" in s["triggers"]


def test_missing_metrics_respread_and_limited_data():
    cfg = load_config()
    s = score_row(row(drawdown=math.nan), cfg)
    assert s["weight_available"] == 0.9 and s["status"] == "Green"
    sparse = row(net_debt_to_cfo=math.nan, net_debt=5.0, capex_to_cfo=math.nan, fcf_to_debt=math.nan, debt_growth_yoy=math.nan, drawdown=math.nan)
    assert score_row(sparse, cfg)["status"] == "Not rated"
