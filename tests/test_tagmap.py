from aicm.tagmap import Facts


def raw(tag, rows):
    return {"facts": {"us-gaap": {tag: {"units": {"USD": [
        {"start": s, "end": e, "val": v, "filed": f, "accn": a, "form": form} if s else {"end": e, "val": v, "filed": f, "accn": a, "form": form}
        for s, e, v, f, a, form in rows]}}}}}


# fiscal year ends 30 June (like Microsoft)
REV = [
    ("2022-07-01", "2023-06-30", 400, "2023-07-27", "A1", "10-K"),   # FY23 annual
    ("2022-07-01", "2022-09-30", 90, "2022-10-25", "A2", "10-Q"),    # Q1 FY23
    ("2022-07-01", "2022-12-31", 190, "2023-01-24", "A3", "10-Q"),   # H1 FY23
    ("2023-07-01", "2023-09-30", 110, "2023-10-24", "A4", "10-Q"),   # Q1 FY24
    ("2023-07-01", "2023-12-31", 230, "2024-01-23", "A5", "10-Q"),   # H1 FY24
    ("2023-10-01", "2023-12-31", 120, "2024-01-23", "A5", "10-Q"),   # Q2 only (must be ignored)
]


def test_ttm_first_quarter_non_calendar_year():
    f = Facts(raw("Revenues", REV))
    v = f.ttm("revenue", "2023-09-30", "2023-10-24")
    assert v.value == 400 + 110 - 90


def test_ttm_uses_year_to_date_not_the_single_quarter():
    f = Facts(raw("Revenues", REV))
    assert f.ttm("revenue", "2023-12-31", "2024-01-23").value == 400 + 230 - 190


def test_ttm_is_point_in_time():
    f = Facts(raw("Revenues", REV))
    assert f.ttm("revenue", "2023-09-30", "2023-10-01") is None  # the 10-Q was not filed yet


def test_ttm_full_year_is_the_annual_value():
    f = Facts(raw("Revenues", REV))
    assert f.ttm("revenue", "2023-06-30", "2023-07-27").value == 400


def test_second_algorithm_agrees_on_a_calendar_year_company():
    rows = [
        ("2022-01-01", "2022-03-31", 100, "2022-04-28", "C1", "10-Q"), ("2022-01-01", "2022-06-30", 210, "2022-07-28", "C2", "10-Q"),
        ("2022-01-01", "2022-09-30", 330, "2022-10-27", "C3", "10-Q"), ("2022-01-01", "2022-12-31", 460, "2023-02-02", "C4", "10-K"),
        ("2023-01-01", "2023-03-31", 120, "2023-04-27", "C5", "10-Q"), ("2023-01-01", "2023-06-30", 250, "2023-07-27", "C6", "10-Q"),
        ("2023-01-01", "2023-09-30", 390, "2023-10-26", "C7", "10-Q"),
    ]
    f = Facts(raw("Revenues", rows))
    assert f.ttm("revenue", "2023-09-30", "2023-10-26").value == 460 + 390 - 330 == 520
    assert f.discrete_quarters_sum("revenue", "2023-09-30", "2023-10-26") == 520


def test_tags_are_merged_across_a_concept():
    # the annual figure sits under one tag, the quarter under another
    r = {"facts": {"us-gaap": {
        "Revenues": {"units": {"USD": [{"start": "2022-07-01", "end": "2023-06-30", "val": 400, "filed": "2023-07-27", "accn": "A1", "form": "10-K"}]}},
        "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
            {"start": "2023-07-01", "end": "2023-09-30", "val": 110, "filed": "2023-10-24", "accn": "A4", "form": "10-Q"},
            {"start": "2022-07-01", "end": "2022-09-30", "val": 90, "filed": "2023-10-24", "accn": "A4", "form": "10-Q"}]}}}}}
    assert Facts(r).ttm("revenue", "2023-09-30", "2023-10-24").value == 420


def test_debt_components_and_short_term():
    def inst(tag, v):
        return {tag: {"units": {"USD": [{"end": "2024-03-31", "val": v, "filed": "2024-04-30", "accn": "B1", "form": "10-Q"}]}}}
    g = {}
    for t, v in [("LongTermDebtNoncurrent", 100), ("LongTermDebtCurrent", 10), ("CommercialPaper", 5)]:
        g.update(inst(t, v))
    assert Facts({"facts": {"us-gaap": g}}).debt("2024-03-31", "2024-04-30").value == 115
    g2 = inst("LongTermDebt", 200)
    assert Facts({"facts": {"us-gaap": g2}}).debt("2024-03-31", "2024-04-30").value == 200
