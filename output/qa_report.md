# Data QA report

Result: **PASS**

## Tie-out to the 10-K's own annual figures (TTM at the latest fiscal year-end, 1% tolerance)

| Company | Item | Fiscal year end | Ours ($bn) | 10-K annual ($bn) | Gap | Status |
| --- | --- | --- | --- | --- | --- | --- |
| MSFT | revenue | 2026-06-30 | 331.84 | 331.84 | 0.000% | pass |
| MSFT | cfo | 2026-06-30 | 182.94 | 182.94 | 0.000% | pass |
| NVDA | revenue | 2026-01-25 | 215.94 | 215.94 | 0.000% | pass |
| NVDA | cfo | 2026-01-25 | 102.72 | 102.72 | 0.000% | pass |
| META | revenue | 2025-12-31 | 200.97 | 200.97 | 0.000% | pass |
| META | cfo | 2025-12-31 | 115.80 | 115.80 | 0.000% | pass |

## Checks per company

| Company | Check | Status | Detail |
| --- | --- | --- | --- |
| MSFT | freshness | pass | latest period end 2026-09-30 (35 days before the newest filing in the universe) |
| MSFT | complete_latest | pass | all items present |
| MSFT | year_on_year_available | pass | prior-year period found |
| MSFT | ttm_two_algorithms | pass | worst gap 0.00% across 4 periods x 4 items |
| MSFT | sanity | pass | values in plausible ranges |
| MSFT | debt_vs_reported_total | pass | our debt 35.48bn vs LongTermDebt 35.48bn (0.0% apart) |
| MSFT | liquid_assets_vs_reported_total | pass | our cash + investments 64.5bn vs reported 64.5bn (0.0% apart) |
| GOOGL | freshness | pass | latest period end 2026-09-30 (35 days before the newest filing in the universe) |
| GOOGL | complete_latest | pass | all items present |
| GOOGL | year_on_year_available | pass | prior-year period found |
| GOOGL | ttm_two_algorithms | pass | worst gap 0.00% across 4 periods x 4 items |
| GOOGL | sanity | pass | values in plausible ranges |
| GOOGL | debt_vs_reported_total | info | no reported total-debt tag to compare; built from LongTermDebtNoncurrent+LongTermDebtCurrent |
| GOOGL | liquid_assets_vs_reported_total | pass | our cash + investments 265.1bn vs reported 265.1bn (0.0% apart) |
| AMZN | freshness | pass | latest period end 2026-09-30 (35 days before the newest filing in the universe) |
| AMZN | complete_latest | pass | all items present |
| AMZN | year_on_year_available | pass | prior-year period found |
| AMZN | ttm_two_algorithms | pass | worst gap 0.00% across 4 periods x 4 items |
| AMZN | sanity | pass | values in plausible ranges |
| AMZN | debt_vs_reported_total | pass | our debt 180.33bn vs LongTermDebt 180.89bn (0.3% apart) |
| META | freshness | pass | latest period end 2026-09-30 (35 days before the newest filing in the universe) |
| META | complete_latest | pass | all items present |
| META | year_on_year_available | pass | prior-year period found |
| META | ttm_two_algorithms | pass | worst gap 0.00% across 4 periods x 4 items |
| META | sanity | pass | values in plausible ranges |
| META | debt_vs_reported_total | info | no reported total-debt tag to compare; built from LongTermDebtNoncurrent+LongTermDebtCurrent |
| APLD | freshness | pass | latest period end 2026-08-31 (65 days before the newest filing in the universe) |
| APLD | complete_latest | pass | all items present |
| APLD | year_on_year_available | pass | prior-year period found |
| APLD | ttm_two_algorithms | pass | worst gap 0.00% across 4 periods x 4 items |
| APLD | sanity | pass | values in plausible ranges |
| APLD | debt_vs_reported_total | info | no reported total-debt tag to compare; built from LongTermNotesPayable+NotesPayableCurrent |
| EQIX | freshness | pass | latest period end 2026-09-30 (35 days before the newest filing in the universe) |
| EQIX | complete_latest | pass | all items present |
| EQIX | year_on_year_available | pass | prior-year period found |
| EQIX | ttm_two_algorithms | pass | worst gap 0.00% across 4 periods x 4 items |
| EQIX | sanity | pass | values in plausible ranges |
| EQIX | debt_vs_reported_total | pass | our debt 22.84bn vs LongTermDebt 22.84bn (0.0% apart) |
| NVDA | freshness | pass | latest period end 2026-07-26 (101 days before the newest filing in the universe) |
| NVDA | complete_latest | pass | all items present |
| NVDA | year_on_year_available | pass | prior-year period found |
| NVDA | ttm_two_algorithms | pass | worst gap 0.00% across 4 periods x 4 items |
| NVDA | sanity | pass | values in plausible ranges |
| NVDA | debt_vs_reported_total | pass | our debt 33.37bn vs LongTermDebt 33.37bn (0.0% apart) |
| AMD | freshness | pass | latest period end 2026-09-26 (39 days before the newest filing in the universe) |
| AMD | complete_latest | pass | all items present |
| AMD | year_on_year_available | pass | prior-year period found |
| AMD | ttm_two_algorithms | pass | worst gap 0.00% across 4 periods x 4 items |
| AMD | sanity | pass | values in plausible ranges |
| AMD | debt_vs_reported_total | info | no reported total-debt tag to compare; built from LongTermDebtNoncurrent+LongTermDebtCurrent |
| AVGO | freshness | pass | latest period end 2026-08-02 (94 days before the newest filing in the universe) |
| AVGO | complete_latest | pass | all items present |
| AVGO | year_on_year_available | pass | prior-year period found |
| AVGO | ttm_two_algorithms | pass | worst gap 0.00% across 4 periods x 4 items |
| AVGO | sanity | pass | values in plausible ranges |
| AVGO | debt_vs_reported_total | pass | our debt 59.42bn vs LongTermDebt 59.42bn (0.0% apart) |
| MU | freshness | pass | latest period end 2026-09-03 (62 days before the newest filing in the universe) |
| MU | complete_latest | pass | all items present |
| MU | year_on_year_available | pass | prior-year period found |
| MU | ttm_two_algorithms | pass | worst gap 0.00% across 4 periods x 4 items |
| MU | sanity | pass | values in plausible ranges |
| MU | debt_vs_reported_total | warn | our debt 5.18bn vs LongTermDebt 2.79bn (85.5% apart) |
| INTC | freshness | pass | latest period end 2026-09-26 (39 days before the newest filing in the universe) |
| INTC | complete_latest | pass | all items present |
| INTC | year_on_year_available | pass | prior-year period found |
| INTC | ttm_two_algorithms | pass | worst gap 0.00% across 4 periods x 4 items |
| INTC | sanity | pass | values in plausible ranges |
| INTC | debt_vs_reported_total | info | no reported total-debt tag to compare; built from LongTermDebtNoncurrent+DebtCurrent |
| DELL | freshness | pass | latest period end 2026-07-31 (96 days before the newest filing in the universe) |
| DELL | complete_latest | pass | all items present |
| DELL | year_on_year_available | pass | prior-year period found |
| DELL | ttm_two_algorithms | pass | worst gap 0.00% across 4 periods x 4 items |
| DELL | sanity | pass | values in plausible ranges |
| DELL | debt_vs_reported_total | pass | our debt 34.47bn vs LongTermDebt 34.47bn (0.0% apart) |
| VRT | freshness | pass | latest period end 2026-09-30 (35 days before the newest filing in the universe) |
| VRT | complete_latest | pass | all items present |
| VRT | year_on_year_available | pass | prior-year period found |
| VRT | ttm_two_algorithms | pass | worst gap 0.00% across 4 periods x 4 items |
| VRT | sanity | pass | values in plausible ranges |
| VRT | debt_vs_reported_total | pass | our debt 2.93bn vs LongTermDebt 2.93bn (0.0% apart) |

Tie-outs compare against the filings' own XBRL values, not a manual read of the PDF filings. At a fiscal year-end the TTM figure is the reported annual value itself, so this confirms period selection and units, not independent accuracy; the two-algorithm check and the reported-total checks above are the independent tests.
