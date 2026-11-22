# AI Leaders Credit Monitor: Project Report

*22 November 2026. Demonstration on public data. Not investment advice.*

## Summary

The project is a working credit monitor for 13 public AI-infrastructure companies, built from SEC filings and market prices. It scores each company from 0 to 100, labels it Green, Amber or Red, raises alerts when thresholds are crossed, and writes a short credit note whose numbers are filled in by code and verified before publication. Anthropic is listed last and will be scored after its first 10-Q.

Headline finding from the latest data (newest filing 4 November 2026): the 13 companies spend about $685bn a year on capex against about $988bn of operating cash flow, so in aggregate the buildout is still funded from cash flow. Debt, however, is about $647bn, up about 90% in a year, and three names (Amazon, Equinix, Applied Digital) already spend more on capex than they generate.

Code, results and README are on the `main` branch of the project's [GitHub repository](https://github.com/Novapranay/Credit-monitoring-using-LLM-based-systems). This report describes what was built, how it works, what it shows, and where it is weak.

## Purpose and audience

The project asks a lender's version of "is AI a bubble?": who is paying for AI infrastructure with borrowed money, and can their cash flows carry it? An equity investor asks whether prices are too high; a credit analyst asks whether obligors can keep paying and refinancing if AI revenue disappoints. The monitor answers the second question with numbers taken from company filings.

It is built for finance enthusiasts and professionals who want to follow the fast-changing AI market, not for the companies themselves. Metrics use standard credit terms with a brief note on why each matters, and notes avoid any buy, sell or price-target language.

It also serves as a portfolio project for an internship application to Barclays' Structured Credit Trading team in Mumbai, whose role includes monitoring the credit performance of obligors and summarising information with AI tools. The project mirrors that workflow on public data: monitoring, early-warning scoring, alerts, and AI summaries that are controlled rather than trusted.

## Universe

Thirteen companies are scored, covering every layer of the AI stack; Anthropic is listed last and pending. Names were chosen as AI leaders with public filings, then narrowed by one rule: drop companies whose public data is too unreliable to score.

| Layer | Companies |
| --- | --- |
| Hyperscalers | Microsoft, Alphabet, Amazon, Meta Platforms |
| AI data centres and REITs | Applied Digital, Equinix |
| Chips | NVIDIA, AMD, Broadcom, Micron, Intel |
| AI servers, power and cooling | Dell Technologies, Vertiv |
| AI model developer (pending) | Anthropic |

**Anthropic** listed in November 2026 and has so far filed only a registration statement, so the SEC data holds no quarterly financials for it. It stays on the watchlist as "Pending first 10-Q" and flips to scored automatically once a 10-Q or 10-K with revenue appears.

**Dropped, and why**

| Company | Reason |
| --- | --- |
| Nebius, IREN | Removed at the owner's request |
| Oracle, CoreWeave, Super Micro | Recent filings do not tag total debt cleanly, so leverage cannot be computed reliably. Oracle and CoreWeave are among the most debt-funded AI builders, so their absence makes the aggregate picture look calmer |

Metrics were also dropped where the underlying data proved inconsistent: EBITDA (depreciation and amortisation tagged inconsistently), interest coverage (interest expense tagged inconsistently and reduced by capitalised interest), lease-adjusted debt (lease tags stale for several names), plus news-headline tagging and the credit-spread backdrop.

## Data sources and how data flows

Everything the monitor scores comes from two free public sources. Nothing is scraped from news or social media, and no paid data is used.

- **SEC EDGAR XBRL company-facts API (data.sec.gov).** The filed financial statements of each company in machine-readable form: revenue, operating income, operating cash flow, capital expenditure, cash, short-term investments, current assets and liabilities, and every debt line. One JSON file per company, keyed by the company's CIK number.
- **Yahoo Finance chart API (query1 and query2).** Daily closing prices, used for one metric only: the drawdown from the one-year high. This is an unofficial endpoint, so the monitor treats it as optional and still scores a company if the price call fails.

### How the numbers are built from filings

1. **Tag mapping.** Companies label the same item differently (capex, for example, can sit under one of several XBRL tags). A mapping file lists the tags to try, in order, for each concept. Tags are merged across the list, because a company can report the current period under one tag and the comparison period under another.
2. **Trailing twelve months (TTM).** Flow items such as cash flow are put on a trailing-twelve-month basis: latest annual figure, plus the current year-to-date, minus the same year-to-date a year earlier. A second, independent method (summing the four latest discrete quarters) is run as a cross-check.
3. **Point-in-time.** A figure is only used from the date it was filed. A quarter filed on 4 November is not visible to a score dated 1 November, so the score history is not flattered by hindsight.
4. **Debt.** Debt is the noncurrent portion plus the current portion when a noncurrent tag exists, otherwise a total-debt tag, plus short-term borrowings and commercial paper. Net debt is debt minus cash minus short-term investments.
5. **Gates.** Data that fails the sanity checks (see Verification and QA) is held out of scoring and written to a review folder instead of being scored silently.

### Data flow

Filings and prices are fetched into a raw cache, normalised into one clean table per company, checked, scored, turned into alerts, written up as notes, verified, and published to the watchlist file and the dashboard. Each step reads the file the previous step wrote, so any stage can be re-run on its own.

Fundamentals change only when a company files, so between filings a score moves only through the price-based drawdown metric.

## Metrics and scoring

Each company gets a 0 to 100 risk score from seven metrics, then a Green, Amber or Red status. The scorecard is absolute, not relative: a company is judged against fixed thresholds, not against the other companies in the list. If every name worsens, they all show it.

### The seven metrics

| Metric | What it tells you | Weight | 0 risk points at | 4 risk points at |
| --- | --- | --- | --- | --- |
| Net debt / operating cash flow | Years of cash flow needed to repay net debt | 25 | 1.0 years or less | 5.0 years or more |
| Capex / operating cash flow | How much of cash flow is spent on buildout | 20 | 60% or less | 150% or more |
| Free cash flow / debt | Cash left after capex, relative to debt | 15 | 40% or more | 0% or less |
| Debt growth, year on year | How fast borrowing is rising | 15 | 10% or less | 100% or more |
| Current ratio | Short-term assets against short-term bills | 10 | 1.5 or more | 0.8 or less |
| Operating margin change, year on year | Whether profitability is eroding | 5 | no fall | a fall of 10 points or more |
| Share price drawdown from one-year high | Market stress, as a cross-check | 10 | 15% or less | 55% or more |

Between the two ends, risk points rise in a straight line through five thresholds (for example, net debt / cash flow earns 1 point at 2.0 years, 2 at 3.0 and 3 at 4.0). A company with net cash scores zero on net debt and on free cash flow / debt.

### From points to a score

1. Each metric's 0 to 4 points are multiplied by its weight and added up, then scaled to 0 to 100.
2. If a metric is missing, the score is rescaled over the metrics that are available. If less than 60% of the total weight is available, the company is shown as **Not rated** instead of being scored on thin data.
3. **Green** is below 30, **Amber** is 30 to 55, **Red** is above 55.

### Triggers that override the score

- **Forces Red:** operating cash flow is not positive while debt is outstanding.
- **Forces at least Amber:** capex is above 150% of operating cash flow, or debt has more than doubled in a year.

The weights and thresholds are judgment, written in one config file (`config/score_config.yaml`) so a reader can disagree with them and change them. They are not fitted to defaults or ratings. The dashboard's Company tab shows each metric's points and what moved the score since the last filing.

A score changes between runs only when a new filing arrives or the price-based drawdown moves. Alerts are raised for a change of status, for any metric that reaches 3 or more of its 4 risk points (marked new or standing), and for any trigger.

## System architecture

The system is eleven single-purpose agents run in order by one orchestrator, in five stages with three gates. Each agent reads a file and writes a file, so any stage can be re-run and inspected on its own. Every agent is plain deterministic code except the Writer, and even the Writer cannot publish anything the Verifier has not passed.

| # | Agent | Stage | Job |
| --- | --- | --- | --- |
| 0 | Orchestrator | all | Runs the stages in order, stops at a failed gate, logs each run |
| 1 | Universe | Ingest | Holds the company list and CIK numbers; keeps Anthropic pending until its financials are tagged |
| 2 | Filings | Ingest | Downloads SEC company facts, cached and rate-limited |
| 3 | Market | Ingest | Downloads daily prices and works out the one-year-high drawdown |
| 4 | Tag-mapper | Normalise | Maps XBRL tags to standard items; builds quarterly and trailing-twelve-month series dated by filing date |
| 5 | Data QA | Normalise | Cross-checks the numbers; can stop the run |
| 6 | Metrics | Analyse | Computes the seven credit ratios per quarter |
| 7 | Scoring | Analyse | Points, weights, 0 to 100 score, status, triggers and a "why it moved" explanation |
| 8 | Alerts | Analyse | Metric breaches, status changes and the AI-bubble totals |
| 9 | Writer | Publish | Drafts each company note as prose with placeholders, never digits |
| 10 | Verifier | Publish | Six checks per note, then a mutation test of the checks themselves |
| 11 | Publisher | Publish | Writes the watchlist file, the alert digest, the verified notes and the dashboard |

### The three gates

1. **All active companies downloaded.** If a company's SEC data is missing, the run stops rather than scoring a smaller list without saying so.
2. **Data QA passes.** Numbers that disagree between two methods, or fall outside plausible ranges, stop the run.
3. **Only verified notes are published.** A note that fails any check goes to a review folder and is never shown.

### Why the Writer never types a number

The risk with AI-written summaries is a confident wrong number. So the Writer produces sentences with placeholders such as capex-to-cash-flow, and the Verifier fills each one from the computed tables only after the note passes. The default writer is a template. An optional LLM writer can be switched on with an environment variable and an API key; it works under the same rules and the same Verifier, but it has not been run yet because no key was available during the build.

## Verification and QA

There are two separate layers of checking: one for the data going in, one for the words coming out.

### Data QA (before scoring)

- **Two independent TTM methods must agree.** Year-to-date arithmetic is compared with the sum of the four latest discrete quarters. A disagreement stops the run.
- **Reported totals as a cross-check.** Where a company reports its own total debt or cash-plus-investments tag, ours must roughly match it. Micron's reported long-term-debt tag disagrees with our figure, which includes finance leases, so QA raises a warning for it.
- **Sanity ranges.** Values must fall in plausible ranges (revenue, for example, must be positive).
- **Fiscal-year-end tie-out.** For Microsoft, NVIDIA and Meta, the TTM at fiscal year end must equal the annual figure in the 10-K. This mostly confirms that periods and units were picked correctly, so it is a weaker check than it sounds.

The full result is in `output/qa_report.md`.

### Note verification (before publishing)

Every note passes six checks before any number is filled in:

1. No raw digits anywhere in the draft.
2. Every placeholder names a known metric that has a value for that company.
3. Direction words (rose, fell) agree with the sign of the change, and qualitative claims agree with the data.
4. Citations are SEC filings the monitor actually used.
5. The watch level and status wording match the rules, and there is no buy or sell language.
6. All five note sections are present.

### Mutation test

To test the checks, each note is deliberately corrupted in up to nine ways (a typed number, an unknown metric, a flipped direction word, an invented citation, a wrong watch level, buy/sell language, a missing section, a wrong status phrase, a false qualitative claim). **110 of 110 corrupted notes were rejected, and every unmodified note passed first.**

Read that result carefully. It shows that each check fires on the error it was written for. It is a regression test, not an estimate of how well the Verifier would catch an error nobody anticipated. The result is in `output/mutation_report.md`.

### Tests

Sixteen automated tests cover the TTM maths, the scoring bands and triggers, and the verifier. They pass on the committed code.

## Results

Across the 13 scored companies, the AI buildout is still mostly paid for by cash flow, but the borrowing behind it is growing fast. Trailing-twelve-month capex is about $685bn against operating cash flow of about $988bn, so capex takes 69% of cash flow. Total debt is about $647bn, up 90% from about $340bn a year earlier. Three companies spend more on capex than they generate in operating cash flow: Amazon, Equinix and Applied Digital. Figures are from filings up to 4 November 2026.

### Watchlist

| Company | Status | Score (0 to 100) | Capex / operating cash flow | Net debt / operating cash flow | Debt growth, year on year |
| --- | --- | --- | --- | --- | --- |
| Applied Digital (APLD) | Red | 85 | 1,995% | 14.6x | +828% |
| Equinix (EQIX) | Red | 62 | 140% | 4.6x | +32% |
| Amazon (AMZN) | Amber | 51 | 128% | 0.4x | +228% |
| Meta (META) | Amber | 30 | 78% | 0.0x | +190% |
| Alphabet (GOOGL) | Amber | 27 | 89% | net cash | +374% |
| NVIDIA (NVDA) | Amber | 23 | 5% | net cash | +294% |
| AMD (AMD) | Amber | 20 | 23% | net cash | +120% |
| Dell (DELL) | Green | 29 | 30% | 1.9x | +20% |
| Intel (INTC) | Green | 15 | 78% | net cash | +8% |
| Vertiv (VRT) | Green | 11 | 14% | net cash | +0% |
| Micron (MU) | Green | 9 | 34% | net cash | -64% |
| Broadcom (AVGO) | Green | 5 | 3% | 0.9x | -7% |
| Microsoft (MSFT) | Green | 5 | 69% | net cash | -18% |
| Anthropic (ANT) | Pending first 10-Q | not scored | not scored | not scored | not scored |

### What the picture says

- **Two names are Red for different reasons.** Applied Digital spends about twenty times its operating cash flow on capex and has net debt of nearly 15 years of cash flow: it is debt-financed growth. Equinix is a data-centre REIT whose capex is growth spending by design, so it scores Red mainly on structure. Read it as a leveraged benchmark, not a distress signal.
- **Amazon is the one hyperscaler out-spending its cash flow.** Capex is 128% of operating cash flow and debt is up 228%, though net debt is still small at 0.4 years of cash flow.
- **Amber is mostly the debt-doubling trigger.** All five Amber names have debt that more than doubled in a year. NVIDIA, AMD and Alphabet are net cash and started from a low base, so for them Amber is a flag, not a worry. Meta also lost about 10 points of operating margin.
- **Most Green names have room.** Microsoft funds very large capex (69% of cash flow) with little debt. Dell is the closest Green to the line at 29, with 1.9 years of cash flow in net debt and thin margins.

### Is AI a bubble, from a lender's view?

On this evidence, not yet a credit bubble across this group: operating cash flow still covers 1.4 times the capex bill. The warning sign is the direction, not the level. Debt is up 90% in a year, and the most leveraged names are the smaller ones. The group also leaves out Oracle and CoreWeave, two of the heaviest debt-funded builders, so the true picture is probably less calm than these totals (see Limitations). This is a screening view from public data, not investment advice.

## Limitations

The monitor is a screening tool built on public filings. These are the known weaknesses, in rough order of how much they could change a conclusion.

1. **The universe leaves out some of the most debt-funded builders.** Oracle, CoreWeave and Super Micro were dropped because their recent filings do not tag total debt cleanly. Nebius and IREN were removed at the project owner's request. The aggregate therefore looks calmer than the whole market.
2. **Off-balance-sheet financing is invisible.** Data-centre joint ventures and leases not yet started are not in reported debt, so leverage can be understated for some hyperscalers.
3. **The scorecard is judgment.** Weights and thresholds are chosen, not estimated from defaults. Equinix, a REIT, scores Red mainly on structure. The debt-doubling trigger puts cash-rich NVIDIA, AMD and Alphabet on Amber.
4. **Debt tags differ by company.** The source tag used is recorded per company in the processed metrics file. Micron's reported long-term-debt tag disagrees with our figure, which includes finance leases, and QA flags it.
5. **The price metric is an equity signal, not a credit signal.** Bond prices, credit default swap spreads and ratings are not free, so they are not used.
6. **Fundamentals are not daily.** Balance sheets and cash flows change only when a company files. Only the drawdown moves daily.
7. **Prices come from an unofficial Yahoo endpoint** that can change or break without notice.
8. **Anthropic is not scored.** It has only a registration statement so far and shows as pending its first 10-Q.
9. **The LLM writer is untested.** No API key was available, so only the template writer has run. The Verifier applies equally to both.
10. **The verification results are regression tests.** The mutation test shows each check fires on the error it targets. The fiscal-year-end tie-out mostly confirms period and unit selection.

None of this is investment advice. It is a demonstration on public data.

## How to run it and where things are

The code is in the GitHub repository [Novapranay/Credit-monitoring-using-LLM-based-systems](https://github.com/Novapranay/Credit-monitoring-using-LLM-based-systems). It ships with processed results, so the dashboard works straight after cloning.

```bash
pip install -r requirements.txt
python run.py            # use cached SEC data and prices; add --refresh to re-download
streamlit run app.py     # open the dashboard
python -m pytest -q tests
```

Before using `--refresh`, set the `SEC_USER_AGENT` environment variable to a descriptive string with your contact details, as the SEC's fair-access policy requires. To use the optional LLM writer, set `AICM_USE_LLM=1` and `ANTHROPIC_API_KEY` and install the `anthropic` package.

### Repository layout

| Path | What is in it |
| --- | --- |
| `config/` | Company list, XBRL tag map, and the scorecard weights and thresholds |
| `src/aicm/` | The eleven agents and shared helpers |
| `run.py` | The orchestrator |
| `app.py` | The Streamlit dashboard: Watchlist, Company, AI-bubble lens, Method and QA |
| `data/processed/` | Metrics, scores, alerts and AI-bubble totals (committed) |
| `output/` | Watchlist file, alert digest, verified notes, review folder, QA report, mutation report |
| `tests/` | Tests for the TTM maths, scoring and verifier |
| `docs/` | This report and dashboard screenshots |

### Changing the scorecard

Every weight, threshold and trigger sits in `config/score_config.yaml`. Edit a number, re-run `python run.py`, and the watchlist, notes and dashboard update. Adding a company means one entry in `config/universe.yaml`, plus a tag-map fallback if its filings use unusual debt tags.

## Next steps

1. **Score Anthropic** once its first 10-Q is filed and its revenue and cash flow are tagged.
2. **Add Oracle and CoreWeave back** after hand-checking their debt lines, since they are the biggest gap in the picture.
3. **Test the LLM writer** with an API key, run it through the same Verifier and mutation test, and compare its notes with the template's.
4. **Refresh on a schedule.** Run the pipeline daily or after each filing wave so the watchlist stays current without manual work.
5. **Add market-implied credit signals** such as bond spreads or credit default swap data if a source becomes available, to complement the equity-based drawdown.
6. **Account for off-balance-sheet commitments** by reading lease and joint-venture disclosures for the hyperscalers.
7. **Test the weights.** Compare the scorecard against known stress episodes in other sectors to see whether the thresholds are sensible, and publish the sensitivity of rankings to the weights.
